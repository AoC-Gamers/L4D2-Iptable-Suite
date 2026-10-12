# QEMU transaction and boot integration exercise

`tests/vm/transactions.py` exercises the installed production nftables entrypoint,
its systemd rollback timer, a second authenticated SSH connection, and the
`l4d2-firewall.service` boot restore. It deliberately uses the production state
directory `/var/lib/l4d2-firewall` and changes the guest firewall. Run it only in
the dedicated disposable QEMU guest prepared by the orchestrator.

## Safety boundary and prerequisites

Every phase refuses to proceed unless all of these hold:

- The process is root, PID 1 is systemd, and `systemd-detect-virt --vm` reports
  `qemu` or `kvm`.
- The orchestrator has created `/run/l4d2-suite-vm.json`, owned by root with mode
  `0600`, containing exactly `{"virtualization":"qemu","disposable":true}`.
  `/run` is volatile, so recreate this marker after every reboot before invoking
  the post-reboot phase.
- The trusted suite is installed at `/opt/l4d2-firewall`, and the loaded
  `l4d2-firewall.service` runs its `core/fw.py load --local` entrypoint.
- The production state has no `current.json`, `pending.json`, or `persisted.json`
  before `bootstrap`. A non-empty state is a hard failure; the harness does not
  remove or overwrite it.

Missing tools, unavailable systemd, failed SSH, invalid unit state, and incomplete
kernel support are failures, never skips. The harness does not change host
firewall state, network namespaces, host SSH configuration, or host services.
The VM orchestrator must keep its ephemeral SSH key and known-hosts file outside
the guest and must connect to the guest through the QEMU forwarding endpoint.

## Orchestrated phases

Run the script as root in `/opt/l4d2-firewall/tests/vm/transactions.py`. Run
`bootstrap` from the guest console or a trusted provisioning step. It installs a
minimal SSH policy that permits the QEMU user-network host (`10.0.2.2/32`), saves
that confirmed policy, and enables the real boot unit. It fails unless current
and persisted policy match and the generated nftables objects exist.

For the fresh-authentication check, run `arm-fresh-ssh` from the first SSH session
to the guest. It applies a timed SSH policy change and verifies that the
production transient `l4d2-rollback-TOKEN.timer` is active. Then terminate that
session and open a separate SSH connection using a new TCP session. From that
second authenticated connection, run `confirm-fresh-ssh TOKEN`. The guest checks
that `SSH_CONNECTION` differs from the applicator connection before it confirms
and saves the candidate. The orchestrator must not use SSH connection multiplexing
for this step.

For the process-death check, run `arm-kill-worker`. It starts a separate guest
worker that calls the real `Store.apply_locked` path with the real systemd
watchdog. The test-only `engine.execute` wrapper first calls the original engine
to commit the candidate, then writes a marker and stalls while still holding the
writer lock. The phase returns only after checking that the pending journal and
predecessor are durable, the candidate is active, and the rollback timer is
active. Run `kill-committed-worker`; it validates the recorded PID and sends that
worker `SIGKILL`. After the monotonic deadline, `verify-killed-worker-rollback`
requires the systemd timer to restore the exact predecessor and clear the
matching journal. The wrapper is isolated to this test process and does not
modify product code.

Next, run `arm-abandoned-session` from SSH. It starts a second timed apply and records
the monotonic deadline and confirmed predecessor. Terminate the SSH session
without confirming. After the deadline, run `verify-abandoned-rollback` from the
guest console. It requires the independent systemd timer to have removed the
pending journal, recorded the matching rollback token, restored the exact
predecessor, and left its firewall objects active. This validates session loss
after the apply command has armed and completed the candidate; it does not claim
to simulate a kernel or power failure during the Netfilter commit.

Run `prepare-reboot`, reboot the guest from the external orchestrator, recreate
the QEMU marker in `/run`, then run `post-reboot`. That phase checks that the
persisted nftables policy was restored byte-for-byte into `current`, that the
real unit completed with `Result=success` and remains active, and that its
registered nftables objects are present. `cleanup` disables only those owned
objects, disables the boot unit, removes persisted policy, and retains a small
test-sequence marker that prevents starting the legacy exercise early.

The legacy exercise is a separate backend check and runs only after the nftables
post-reboot phase and cleanup. `bootstrap-legacy` requires that sequence marker
and an otherwise empty production state. It explicitly requests
`IPTABLES_FRONTEND=legacy`, applies and saves an SSH-only policy, then verifies
the selected frontend and registered chains/hooks. Foreign chains or moved
hooks cause a failure; the harness never changes system alternatives or removes
unregistered rules. Run `prepare-reboot-legacy`, reboot from the orchestrator,
recreate the QEMU marker, then run `post-reboot-legacy`. It verifies that the
persisted iptables policy and the actual resolved frontend are both `legacy`,
and that the boot unit restored its registered chains/hooks. Finish with
`cleanup-legacy`, which snapshots all rules outside registered chains and exact
suite hooks, removes only registered legacy objects, and checks that the foreign
snapshot is unchanged before disabling the unit and removing test persistence.

The lifecycle is:

```text
bootstrap -> arm-fresh-ssh -> [new SSH connection] confirm-fresh-ssh TOKEN
          -> arm-kill-worker -> kill-committed-worker -> [wait past deadline]
          -> verify-killed-worker-rollback
          -> arm-abandoned-session -> [drop SSH; wait past deadline]
          -> verify-abandoned-rollback -> prepare-reboot -> reboot
          -> [recreate /run marker] post-reboot -> cleanup
          -> bootstrap-legacy -> prepare-reboot-legacy -> reboot
          -> [recreate /run marker] post-reboot-legacy -> cleanup-legacy
```

Before using the VM, run `python3 -I tests/vm/test_transactions_harness.py` from
the checkout. This unit test substitutes the store/process boundary and asserts
that the parent can publish the manifest and SIGKILL the simulated worker without
trying to acquire the writer lock it holds. It does not execute Netfilter commands.

## Evidence and limits

Each phase prints a compact JSON result. Preserve orchestrator logs alongside
the QEMU image identity, guest kernel version, systemd version, and SSH connection
details (redact key material and the confirmation token once complete). A pass
establishes behavior only for the exact guest image/kernel/systemd/Netfilter
versions exercised. The first reboot validates nftables restore; the second
validates iptables-legacy restore. Neither certifies Docker daemon integration,
other iptables frontends, another distribution's boot ordering, or a real host
firewall.

### Observed run

The completed disposable guest used kernel `6.8.0-142-generic`, systemd
`255.4-1ubuntu8.17`, nftables `1.0.9`, and iptables `1.8.10`; the legacy
reboot selected `iptables-legacy` for both IPv4 and IPv6. Both reboot cycles had
different boot IDs from their predecessors, and the volatile safety marker was
recreated only after QEMU/KVM was rechecked.

| Exercise | Result |
| --- | --- |
| New authenticated SSH connection confirms the timed nftables candidate | PASS; distinct `SSH_CONNECTION`, saved digest `bdc582b6e99a775edf85cabf28f22048233ef5e3e3af682b99ed5a462b13f3c3` |
| SIGKILL after candidate commit, followed by the systemd watchdog deadline | PASS; predecessor restored and pending journal cleared |
| Applicator SSH session abandoned, followed by the systemd watchdog deadline | PASS; predecessor restored and pending journal cleared |
| nftables persistence across reboot | PASS; unit `Result=success`, active, persisted/current digest matched, registered tables present |
| nftables cleanup | PASS; registered tables and persisted/current/pending policy removed |
| `iptables-legacy` persistence across reboot | PASS; unit `Result=success`, active, persisted/current digest `5d5f59a86b7ad6a457be4cb604bdcc0668342c7a2c427985675d7501dc793041`, six chains and two hooks present across IPv4/IPv6 |
| `iptables-legacy` cleanup | PASS; owned chains/hooks removed, unit disabled |

The legacy cleanup comparison did not exercise non-empty foreign user rules:
its pre/post signature contained zero foreign rules and zero foreign user
chains (only six builtin chains across two table/family entries). The matching
signature therefore verifies that cleanup left this empty external snapshot
unchanged; it does not prove preservation of non-empty foreign rules. The
separate Docker integration matrix exercises non-empty foreign rules, but is
not evidence from this transaction cleanup signature. The guest was checked
after cleanup: no owned nftables tables or legacy L4D2 markers remained, and
the service was disabled. It remained active until guest shutdown because
cleanup disables the unit without stopping it.

Detailed sanitized phase output and boot IDs are in
`tmp/vm/transactions.log` in the validation workspace; that log is run evidence,
not part of this repository document.
