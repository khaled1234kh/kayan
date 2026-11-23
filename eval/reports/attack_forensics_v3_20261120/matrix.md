# V3 forensic matrix of the frozen v2 run

Every observation and all 72 responses are represented below. The JSON companion contains raw answer text, full pinned technique definitions, exact reference excerpts, per-field ranking contributions and missing statements by alternative group. Interpretations are AI analyst judgments on fictional records.

[Machine-readable matrix](matrix.json) · [Frozen v2 results](../../../docs/ATTACK_EXPLORATORY_V2_RESULTS_2026-11-20.md)

## quartz · confirmed

The East grant/time and custodian support access. E1.2 is necessary only if the custodian does not independently attest consent. Cloud tenancy is under-specified, so the subtechnique is conditional.

- **E1.1** A paper approval covers the read-only role on unit West through May.
- **E1.2** The duty officer confirms all elevated grants on unit East during the freeze were unauthorized.
- **E2.1** East's permissions diff at 18:04 shows acct-91 acquired persistent owner privileges; grant ledger sequence 73 committed.
- **E2.2** West uses an unrelated numeric account namespace.
- **E3.1** Case custodian: the outside operator controlled East/acct-91 at 18:04.
- **E3.2** An earlier attribution for West is still open.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1098.003 Additional Cloud Roles | [['E1.2', 'E2.1', 'E3.1']] | [15, 15, 7] | [42, 64, 25] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1136.002, T1548.005, T1222, T1222.002, T1222.001 | T1222.001 → E2.1 (unkeyed) | {'T1098.003': [['E1.2', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 1 · bm25_k5 | T1548.005, T1098.002, T1078.004, T1222.002, T1222.001 | T1222.001 → E2.1 (unkeyed) | {'T1098.003': [['E1.2', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1548.005, T1098.002, T1078.004, T1222.002, T1222.001 | T1222.001 → E2.1 (unkeyed) | {'T1098.003': [['E1.2', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1136.002, T1548.005, T1222, T1222.002, T1222.001 | T1222.001 → E2.1 (unkeyed) | {'T1098.003': [['E1.2', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## flint · inconclusive

A queue gap and superseded pager allegation leave the underlying action unresolved. Linux log IDs add an unsupported platform assumption.

- **E1.1** A pager summary repeated a log-clear allegation for WC-14.
- **E1.2** The writer had only seen a gap in the collector queue.
- **E2.1** A later examiner found no corroboration for the alleged clearing on WC-14; the local journal was unavailable.
- **E2.2** The relay's delivery log also ends at the start of the outage.
- **E3.1** The incident record retracted the pager's original conclusion pending a readable source journal.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1685.001, T1685.006, T1027.004, T1070.003, T1685.005 | T1685.006 → E1.1 (unkeyed)<br>T1685.006 → E2.1 (unkeyed)<br>T1685.006 → E2.2 (unkeyed)<br>T1685.006 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 1 · hybrid192_k5 | T1685.001, T1685.006, T1685.004, T1070.003, T1685.005 | T1685.001 → E1.1 (unkeyed)<br>T1685.004 → E1.2 (unkeyed)<br>T1685.005 → E2.1 (unresolved)<br>T1685.006 → E2.2 (unkeyed)<br>T1685.001 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1685.001, T1685.006, T1685.004, T1070.003, T1685.005 | T1685.001 → E1.1 (unkeyed)<br>T1685.004 → E1.2 (unkeyed)<br>T1685.005 → E2.1 (unresolved)<br>T1685.006 → E2.2 (unkeyed)<br>T1685.001 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 2 · bm25_k5 | T1685.001, T1685.006, T1027.004, T1070.003, T1685.005 | T1685.006 → E1.1 (unkeyed)<br>T1685.006 → E2.1 (unkeyed)<br>T1685.006 → E2.2 (unkeyed)<br>T1685.006 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## larch · inconclusive

Captured desktop content exists. Concurrent sessions and missing originating process prevent attribution. Remote services would require independent evidence.

- **E1.1** Examiner cache: three images reproduce the clerk's desktop on PC-18, two seconds apart.
- **E1.2** The acquisition log preserves their creation time but no originating process.
- **E2.1** Support and the unauthorized operator both held sessions on PC-18 in that interval.
- **E2.2** Consent forms identify the support session only; attribution of the images remains open.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1539, T1557.002, T1021.001, T1547.005, T1219.002 | T1557.002 → E1.1 (unkeyed)<br>T1021.001 → E2.1 (unkeyed)<br>T1219.002 → E2.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 1 · hybrid192_k5 | T1021.001, T1497.003, T1563.002, T1219.002, T1563 | T1563.002 → E2.1 (unkeyed)<br>T1021.001 → E1.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1021.001, T1497.003, T1563.002, T1219.002, T1563 | T1563.002 → E2.1 (unkeyed)<br>T1021.001 → E1.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 2 · bm25_k5 | T1539, T1557.002, T1021.001, T1547.005, T1219.002 | T1557.002 → E1.1 (unkeyed)<br>T1021.001 → E2.1 (unkeyed)<br>T1219.002 → E2.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## ochre · confirmed

Either the audit or alternate image identifies the enabled forward with revision and creator. Both need the same session attribution. Revision 11 concerns different mechanics.

- **E1.1** The managed tenant's mail-rule audit records an enabled outside-forward on board@east under session VR9, revision 12.
- **E2.1** A collector at the recovery site independently imaged the enabled board@east forwarding rule and its revision-12 creator session VR9.
- **E2.2** It had also imaged revision 11, a local folder rule.
- **E3.1** Identity response established VR9 belonged to the unapproved intruder monitoring board correspondence during revision 12.
- **E3.2** The department had given its archivist a different session.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1114.003 Email Forwarding Rule | [['E1.1', 'E3.1'], ['E2.1', 'E3.1']] | [1, 1, 1] | [1, 1, 1] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1556.007, T1490, T1114.003, T1585, T1484 | T1114.003 → E1.1 (keyed_support)<br>T1585 → E3.1 (unkeyed)<br>T1490 → E2.1 (unkeyed) | {'T1114.003': [['E3.1'], ['E2.1', 'E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 1 · hybrid192_k5 | T1685.004, T1137.005, T1098.002, T1114.003, T1484 | T1114.003 → E1.1 (keyed_support)<br>T1137.005 → E1.1 (unkeyed)<br>T1484 → E1.1 (unkeyed)<br>T1098.002 → E3.1 (unkeyed)<br>T1685.004 → E2.1 (unkeyed) | {'T1114.003': [['E3.1'], ['E2.1', 'E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1685.004, T1137.005, T1098.002, T1114.003, T1484 | T1114.003 → E1.1 (keyed_support)<br>T1137.005 → E1.1 (unkeyed)<br>T1484 → E1.1 (unkeyed)<br>T1098.002 → E3.1 (unkeyed)<br>T1685.004 → E2.1 (unkeyed) | {'T1114.003': [['E3.1'], ['E2.1', 'E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1556.007, T1490, T1114.003, T1585, T1484 | T1114.003 → E1.1 (keyed_support)<br>T1585 → E3.1 (unkeyed)<br>T1490 → E2.1 (unkeyed) | {'T1114.003': [['E3.1'], ['E2.1', 'E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## pearl · benign

The attachment is stock art and the workstation attribution was withdrawn. The ticket title alone cannot establish capture.

- **E1.1** The screenshot attached to alert 88 is a stock helpdesk image, according to its archived digest.
- **E1.2** The ticket subject reads 'screen capture on packing terminal'.
- **E2.1** The physical terminal produced a printer-status message at 09:20.
- **E2.2** Ticket 88 was corrected to remove the workstation attribution.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1505.005, T1113, T1125, T1027.002, T1558.002 | Empty | None keyed | abstained |
| 1 · hybrid192_k5 | T1113, T1070, T1685.005, T1027.002, T1120 | T1113 → E1.1 (contradicts)<br>T1070 → E2.2 (unkeyed)<br>T1685.005 → E2.1 (unkeyed) | None keyed | extra_technique, finding_on_benign, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1113, T1070, T1685.005, T1027.002, T1120 | T1113 → E1.1 (contradicts)<br>T1070 → E2.2 (unkeyed)<br>T1685.005 → E2.1 (unkeyed) | None keyed | extra_technique, finding_on_benign, citation_without_keyed_support |
| 2 · bm25_k5 | T1505.005, T1113, T1125, T1027.002, T1558.002 | Empty | None keyed | abstained |

Raw response changed between passes for neither arm.

## ash · confirmed

The inventory, job completion and attributed session support a completed purge. Batch and asset linkage make all three relevant. Objective rests on loss of recovery points, without separate motive evidence.

- **E1.1** Snapshot inventory for payroll volume P records recovery points marked absent after purge batch 32.
- **E1.2** The live payroll volume stayed readable.
- **E2.1** The platform's job ledger attributes purge 32 on P to console session U2; the removal finished.
- **E3.1** Custody records identify U2 as the unauthorized intruder session. The recovery operators retained a separate login.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1490 Inhibit System Recovery | [['E2.1', 'E3.1', 'E1.1']] | [1, 16, 2] | [None, 63, 113] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1490, T1680, T1564.004, T1070, T1006 | T1490 → E1.1 (keyed_support)<br>T1006 → E1.1 (unkeyed)<br>T1070 → E1.1 (unkeyed)<br>T1680 → E1.2 (unkeyed)<br>T1564.004 → E1.2 (unkeyed)<br>T1490 → E2.1 (keyed_support)<br>T1070 → E2.1 (unkeyed)<br>T1680 → E3.1 (unkeyed) | {'T1490': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 1 · bm25_k5 | T1490, T1037.002, T1564.004, T1564.014, T1578.001 | T1490 → E1.1 (keyed_support)<br>T1564.004 → E1.1 (unkeyed)<br>T1564.014 → E1.1 (unkeyed)<br>T1578.001 → E1.1 (unkeyed)<br>T1037.002 → E2.1 (unkeyed)<br>T1564.004 → E2.1 (unkeyed)<br>T1564.014 → E2.1 (unkeyed)<br>T1578.001 → E2.1 (unkeyed) | {'T1490': [['E2.1', 'E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1490, T1037.002, T1564.004, T1564.014, T1578.001 | T1490 → E1.1 (keyed_support)<br>T1564.004 → E1.1 (unkeyed)<br>T1564.014 → E1.1 (unkeyed)<br>T1578.001 → E1.1 (unkeyed)<br>T1037.002 → E2.1 (unkeyed)<br>T1564.004 → E2.1 (unkeyed)<br>T1564.014 → E2.1 (unkeyed)<br>T1578.001 → E2.1 (unkeyed) | {'T1490': [['E2.1', 'E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1490, T1680, T1564.004, T1070, T1006 | T1490 → E1.1 (keyed_support)<br>T1006 → E1.1 (unkeyed)<br>T1070 → E1.1 (unkeyed)<br>T1680 → E1.2 (unkeyed)<br>T1564.004 → E1.2 (unkeyed)<br>T1490 → E2.1 (keyed_support)<br>T1070 → E2.1 (unkeyed)<br>T1680 → E3.1 (unkeyed) | {'T1490': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## cedar · confirmed

The Windows receipt and session custody form the principal chain. The restarted audit sequence is plausible corroboration but lacks an independent session or explicit clear alone.

- **E1.1** The overnight sheet mentions a possible log clear on Juniper.
- **E1.2** Desk J was unstaffed until 05:00.
- **E2.1** The retained Windows Security journal receipt on JUN-4 records a completed clear under session 6M.
- **E2.2** The subsequent audit sequence restarts at entry one.
- **E3.1** Incident custody tied 6M on JUN-4 to the unauthorized intruder, after the legitimate operator's token was isolated.
- **E3.2** The separately observed 6N was a supervised maintenance session.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1685.005 Clear Windows Event Logs | [['E2.1', 'E3.1']] | [1, 4, 3] | [1, 1, 1] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1685.006, T1070.003, T1685.005, T1685.004, T1685.001 | T1685.006 → E1.1 (unkeyed)<br>T1685.005 → E2.1 (keyed_support) | {'T1685.005': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 1 · hybrid192_k5 | T1685.006, T1070.003, T1685.005, T1685.004, T1685.001 | T1685.006 → E1.1 (unkeyed)<br>T1685.005 → E2.1 (keyed_support) | {'T1685.005': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1685.006, T1070.003, T1685.005, T1685.004, T1685.001 | T1685.006 → E1.1 (unkeyed)<br>T1685.005 → E2.1 (keyed_support) | {'T1685.005': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1685.006, T1070.003, T1685.005, T1685.004, T1685.001 | T1685.006 → E1.1 (unkeyed)<br>T1685.005 → E2.1 (keyed_support) | {'T1685.005': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## linen · confirmed

The rule journal and identity bind configuration and intent. The gateway corroborates delivery and is not keyed as a substitute for the creator/session link.

- **E1.1** The mailbox rule journal for claims@north shows rule R8 committed under session C4: incoming claim messages were to be copied to box Z.
- **E1.2** The same mailbox has an unrelated team alias.
- **E2.1** Independent gateway journaling linked R8 to copies delivered to Z after the commit.
- **E2.2** The nightly export was empty.
- **E3.1** The incident custodian bound C4 to an unauthorized outsider who controlled Z and sought incoming claims.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1114.003 Email Forwarding Rule | [['E1.1', 'E3.1']] | [4, 2, 1] | [1, 2, 1] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1552.008, T1070.008, T1598.003, T1213.005, T1114.003 | T1114.003 → E1.1 (keyed_support)<br>T1598.003 → E3.1 (unkeyed) | {'T1114.003': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 1 · hybrid192_k5 | T1564.008, T1070.008, T1137.005, T1098.002, T1114.003 | T1564.008 → E1.1 (unkeyed)<br>T1114.003 → E1.1 (keyed_support)<br>T1098.002 → E3.1 (unkeyed) | {'T1114.003': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1564.008, T1070.008, T1137.005, T1098.002, T1114.003 | T1564.008 → E1.1 (unkeyed)<br>T1114.003 → E1.1 (keyed_support)<br>T1098.002 → E3.1 (unkeyed) | {'T1114.003': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1552.008, T1070.008, T1598.003, T1213.005, T1114.003 | T1114.003 → E1.1 (keyed_support)<br>T1598.003 → E3.1 (unkeyed) | {'T1114.003': [['E3.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## slate · confirmed

The file ledger distinguishes availability impact from obfuscation. The backup service and inventory establish a separate recovery event. SE-3/B91 is a different asset and actor.

- **E1.1** IR recorded session B19 as the unauthorized extortionist on archive node SE-2; B91 belongs to its storage administrator.
- **E2.1** File-system ledger on SE-2: B19 encrypted 41 project archives, leaving the drawings unavailable.
- **E2.2** The preview renderer timed out.
- **E3.1** Backup inventory after batch Z: SE-2 lost its last restorable snapshots.
- **E3.2** On the spare SE-3 snapshots were retained.
- **E4.1** Backup service recorded B19 completing the purge of batch Z on SE-2.
- **E4.2** The ticket submitted by B91 referred only to SE-3.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1486 Data Encrypted for Impact | [['E1.1', 'E2.1']] | [15, 72, 17] | [2, 3, 1] |
| T1490 Inhibit System Recovery | [['E1.1', 'E3.1', 'E4.1']] | [14, 137, 41] | [27, 19, 7] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1680, T1558, T1027.011, T1505.006, T1578.001 | T1578.001 → E3.1 (unkeyed)<br>T1680 → E2.1 (unkeyed) | {'T1486': [['E1.1', 'E2.1']], 'T1490': [['E1.1', 'E3.1', 'E4.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 1 · bm25_k5 | T1563, T1027.013, T1558.001, T1558, T1578.001 | T1563 → E2.1 (unkeyed)<br>T1027.013 → E2.1 (unkeyed)<br>T1578.001 → E3.1 (unkeyed)<br>T1578.001 → E3.2 (unkeyed)<br>T1558.001 → E4.1 (unkeyed)<br>T1558 → E4.1 (unkeyed) | {'T1486': [['E1.1', 'E2.1']], 'T1490': [['E1.1', 'E3.1', 'E4.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1563, T1027.013, T1558.001, T1558, T1578.001 | T1563 → E2.1 (unkeyed)<br>T1027.013 → E2.1 (unkeyed)<br>T1578.001 → E3.1 (unkeyed)<br>T1578.001 → E3.2 (unkeyed)<br>T1558.001 → E4.1 (unkeyed)<br>T1558 → E4.1 (unkeyed) | {'T1486': [['E1.1', 'E2.1']], 'T1490': [['E1.1', 'E3.1', 'E4.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1680, T1558, T1027.011, T1505.006, T1578.001 | T1578.001 → E3.1 (unkeyed)<br>T1680 → E2.1 (unkeyed) | {'T1486': [['E1.1', 'E2.1']], 'T1490': [['E1.1', 'E3.1', 'E4.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## silver · benign

The signed record covers the grant and time. A same-name identity from another tenant does not confer attribution. The grant is the correct mechanic but authorized.

- **E1.1** Blue tenant role ledger: finance-review acquired billing administrator at 11:10 under change 418.
- **E1.2** The grant was removed at 12:00.
- **E2.1** The signed duty schedule names finance-review for that billing audit; change 418 covers the full interval.
- **E2.2** The Red tenant had reported a compromised account with the same display name.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1484, T1098.003, T1036.010, T1087.004, T1548.005 | T1484 → E1.1 (unkeyed)<br>T1098.003 → E1.1 (action_only)<br>T1036.010 → E2.2 (unkeyed)<br>T1548.005 → E1.1 (unkeyed) | None keyed | extra_technique, finding_on_benign, citation_without_keyed_support |
| 1 · bm25_k5 | T1484, T1588.003, T1685.004, T1553.002, T1589.003 | Empty | None keyed | abstained |
| 2 · bm25_k5 | T1484, T1588.003, T1685.004, T1553.002, T1589.003 | Empty | None keyed | abstained |
| 2 · hybrid192_k5 | T1484, T1098.003, T1036.010, T1087.004, T1548.005 | T1484 → E1.1 (unkeyed)<br>T1098.003 → E1.1 (action_only)<br>T1036.010 → E2.2 (unkeyed)<br>T1087.004 → E2.2 (unkeyed)<br>T1548.005 → E2.2 (unkeyed) | None keyed | extra_technique, finding_on_benign, citation_without_keyed_support |

Raw response changed between passes for hybrid192_k5.

## fern · inconclusive

Controller errors, missing pre-recovery data and an unrelated unsigned message leave both encryption and intent unverified.

- **E1.1** The shared document store returned unreadable data for 15 minutes.
- **E1.2** A monitoring ticket suspected file encryption.
- **E2.1** Storage staff recovered the volume index but preserved no pre-recovery file sample.
- **E2.2** Controller errors and unaudited write activity overlap the incident window.
- **E3.1** An unsigned extortion message in a different business unit lacked a matching system or time.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1006, T1490, T1027.011, T1680, T1213 | T1027.011 → E1.1 (unkeyed)<br>T1490 → E2.1 (unkeyed)<br>T1006 → E2.2 (unkeyed)<br>T1680 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 1 · bm25_k5 | T1530, T1021.002, T1006, T1490, T1027.011 | T1027.011 → E1.1 (unkeyed)<br>T1021.002 → E1.2 (unkeyed)<br>T1006 → E2.1 (unkeyed)<br>T1490 → E2.2 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 2 · bm25_k5 | T1530, T1021.002, T1006, T1490, T1027.011 | T1027.011 → E1.1 (unkeyed)<br>T1021.002 → E1.2 (unkeyed)<br>T1006 → E2.1 (unkeyed)<br>T1490 → E2.2 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1006, T1490, T1027.011, T1680, T1213 | T1027.011 → E1.1 (unkeyed)<br>T1490 → E2.1 (unkeyed)<br>T1006 → E2.2 (unkeyed)<br>T1680 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_inconclusive, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## opal · failed

The completion criterion excludes the hostile request because the vault refused it and the named recovery point was restored.

- **E1.1** A console transcript attributes a recovery-point deletion request on LAP-9 to a hostile session.
- **E2.1** The retention vault refused the deletion.
- **E2.2** A supervised restore of the named point subsequently passed its content checksum.
- **E3.1** A dashboard ranked the request critical on receipt.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1538, T1561.002, T1621, T1490, T1563 | T1490 → E1.1 (topic_only)<br>T1561.002 → E2.1 (unkeyed)<br>T1563 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_failed, citation_without_keyed_support |
| 1 · bm25_k5 | T1550.003, T1564.014, T1589.003, T1538, T1490 | T1490 → E1.1 (topic_only)<br>T1589.003 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_failed, citation_without_keyed_support |
| 2 · bm25_k5 | T1550.003, T1564.014, T1589.003, T1538, T1490 | T1490 → E1.1 (topic_only)<br>T1589.003 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_failed, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1538, T1561.002, T1621, T1490, T1563 | T1490 → E1.1 (topic_only)<br>T1561.002 → E2.1 (unkeyed)<br>T1563 → E3.1 (unkeyed) | None keyed | extra_technique, finding_on_failed, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## moss · confirmed

The same-frame PID/session join connects the capture to P8. An older binding and legitimate P3 are deliberate conflicts of time and identity.

- **E1.1** Session ledger: operator P3 was using an assigned support account legitimately on station 12.
- **E1.2** Session P8 at station 12 belonged to the intruder and had no authority to observe staff.
- **E2.1** A host capture receipt ties desktop frames 81 and 82 on station 12 to worker pid 62.
- **E2.2** At 09:12 an operator enlarged the dashboard font.
- **E3.1** The kernel session table binds pid 62 to P8 during frames 81 and 82.
- **E3.2** An older table had placed recycled pid 62 in P3 on the previous day.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1113 Screen Capture | [['E1.2', 'E2.1', 'E3.1']] | [16, 105, 49] | [6, 15, 5] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1134.004, T1611, T1564.013, T1219.002, T1021.001 | T1219.002 → E1.1 (unkeyed)<br>T1611 → E2.1 (unkeyed)<br>T1564.013 → E3.1 (unkeyed) | {'T1113': [['E1.2', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 1 · hybrid192_k5 | T1003.001, T1123, T1611, T1538, T1219.002 | T1219.002 → E1.1 (unkeyed)<br>T1611 → E2.1 (unkeyed)<br>T1123 → E2.2 (unkeyed) | {'T1113': [['E1.2', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1003.001, T1123, T1611, T1538, T1219.002 | T1219.002 → E1.1 (unkeyed)<br>T1611 → E2.1 (unkeyed)<br>T1123 → E2.2 (unkeyed) | {'T1113': [['E1.2', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1134.004, T1611, T1564.013, T1219.002, T1021.001 | T1219.002 → E1.1 (unkeyed)<br>T1611 → E2.1 (unkeyed)<br>T1564.013 → E3.1 (unkeyed) | {'T1113': [['E1.2', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## indigo · benign

Continuous host events and delayed delivery explain the relay gap. The named change is a certificate renewal, not local clearing.

- **E1.1** The relay marked K-07 quiet for ten minutes.
- **E1.2** K-07 retained a continuous sequence of Windows Security events during those ten minutes.
- **E2.1** The spool receipt shows delayed delivery after a certificate renewal.
- **E2.2** No change to event collection settings appeared in the signed change journal.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1553.004, T1685.001, T1588.003, T1587.002, T1685.005 | T1553.004 → E1.1 (unkeyed)<br>T1685.001 → E2.1 (unkeyed)<br>T1588.003 → E1.2 (unkeyed)<br>T1685.005 → E2.2 (unkeyed) | None keyed | extra_technique, finding_on_benign, citation_without_keyed_support |
| 1 · hybrid192_k5 | T1685.001, T1546.003, T1653, T1685.005, T1553.005 | T1685.001 → E1.1 (unkeyed)<br>T1685.005 → E1.1 (topic_only)<br>T1685.001 → E1.2 (unkeyed)<br>T1685.005 → E1.2 (contradicts)<br>T1546.003 → E2.1 (unkeyed)<br>T1546.003 → E2.2 (unkeyed) | None keyed | extra_technique, finding_on_benign, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1685.001, T1546.003, T1653, T1685.005, T1553.005 | T1685.001 → E1.1 (unkeyed)<br>T1685.005 → E1.2 (contradicts)<br>T1546.003 → E2.1 (unkeyed)<br>T1546.003 → E2.2 (unkeyed) | None keyed | extra_technique, finding_on_benign, citation_without_keyed_support |
| 2 · bm25_k5 | T1553.004, T1685.001, T1588.003, T1587.002, T1685.005 | T1553.004 → E1.1 (unkeyed)<br>T1685.001 → E1.2 (unkeyed)<br>T1588.003 → E2.1 (unkeyed)<br>T1685.005 → E2.2 (unkeyed) | None keyed | extra_technique, finding_on_benign, citation_without_keyed_support |

Raw response changed between passes for bm25_k5, hybrid192_k5.

## birch · confirmed

The IAM commit and same-tenant principal attribution connect the grant to hostile control. The staging display name is a distractor.

- **E1.1** IAM archive, tenant North: principal w41 gained a standing tenant administrator role in transaction G6.
- **E1.2** The staging tenant carries a different administrator of the same display name.
- **E2.1** IR traced principal w41 in North to the outside operator, who retained its credentials throughout G6 without owner consent.
- **E2.2** The recovery desk locked w41 that afternoon.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1098.003 Additional Cloud Roles | [['E1.1', 'E2.1']] | [3, 68, 12] | [2, 21, 4] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1555.004, T1548.005, T1003.005, T1110.004, T1484 | T1555.004 → E2.1 (unkeyed)<br>T1110.004 → E2.1 (unkeyed)<br>T1484 → E1.1 (unkeyed) | {'T1098.003': [['E1.1', 'E2.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 1 · bm25_k5 | T1098.001, T1074, T1098.003, T1074.002, T1490 | T1098.003 → E1.1 (keyed_support)<br>T1074.002 → E2.1 (unkeyed)<br>T1490 → E2.2 (unkeyed) | {'T1098.003': [['E2.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1098.001, T1074, T1098.003, T1074.002, T1490 | T1098.003 → E1.1 (keyed_support)<br>T1074.002 → E2.1 (unkeyed)<br>T1490 → E2.2 (unkeyed) | {'T1098.003': [['E2.1']]} | correct_id_incomplete_group, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1555.004, T1548.005, T1003.005, T1110.004, T1484 | T1555.004 → E2.1 (unkeyed)<br>T1110.004 → E2.1 (unkeyed)<br>T1484 → E1.1 (unkeyed) | {'T1098.003': [['E1.1', 'E2.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## elm · benign

Scheduled retention was authorized, and recovery from archive succeeded. This is an authorized lookalike.

- **E1.1** Nightly catalogue: three old restore points expired on B7 at midnight.
- **E1.2** The latest restore set remained intact.
- **E2.1** Owner-signed policy specifies that exact retention window and host.
- **E2.2** The offline restore drill recovered all three historical dates from archive.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1201, T1685.001, T1555.004, T1560.002, T1685.005 | Empty | None keyed | abstained |
| 1 · bm25_k5 | T1201, T1686.003, T1553.006, T1553.002, T1552.006 | Empty | None keyed | abstained |
| 2 · bm25_k5 | T1201, T1686.003, T1553.006, T1553.002, T1552.006 | Empty | None keyed | abstained |
| 2 · hybrid192_k5 | T1201, T1685.001, T1555.004, T1560.002, T1685.005 | Empty | None keyed | abstained |

Raw response changed between passes for neither arm.

## hazel · failed

A rejected request and unchanged revision rule out an installed forward. Its separate delivery receipt does not implicate Q7.

- **E1.1** A response analyst associated request Q7 with the intruder already ejected from the tenant.
- **E1.2** Q7 requested a forwarding rule on orders@pine.
- **E2.1** The mail service rejected Q7 before commit; a snapshot on either side has the same rule revision.
- **E2.2** A transport receipt for a separate newsletter reached its usual recipients.

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · bm25_k5 | T1071.003, T1114.003, T1578.001, T1505.002, T1621 | T1114.003 → E2.2 (unlinked)<br>T1071.003 → E2.2 (unkeyed)<br>T1578.001 → E1.1 (unkeyed) | None keyed | extra_technique, finding_on_failed, citation_without_keyed_support |
| 1 · hybrid192_k5 | T1114.003, T1505.002, T1070.008, T1621, T1114 | T1114.003 → E1.2 (topic_only)<br>T1070.008 → E2.1 (unkeyed) | None keyed | extra_technique, finding_on_failed, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1114.003, T1505.002, T1070.008, T1621, T1114 | T1114.003 → E1.2 (topic_only)<br>T1070.008 → E2.1 (unkeyed) | None keyed | extra_technique, finding_on_failed, citation_without_keyed_support |
| 2 · bm25_k5 | T1071.003, T1114.003, T1578.001, T1505.002, T1621 | T1114.003 → E2.2 (unlinked)<br>T1071.003 → E2.2 (unkeyed)<br>T1578.001 → E1.1 (unkeyed) | None keyed | extra_technique, finding_on_failed, citation_without_keyed_support |

Raw response changed between passes for neither arm.

## coral · confirmed

The file journal establishes encrypted replacement and loss of access. Accounting and attribution link the process and session. The record supports impact, with extortion context, not payload obfuscation.

- **E1.1** Case review associates session DK2 with the unauthorized extortionist targeting the drawing store.
- **E1.2** The quarantine of a different workstation was routine.
- **E2.1** Endpoint file journal on DRAW-8 associates writer pid 71 with mass replacement by encrypted content; drawings became unreadable.
- **E3.1** The process accounting log binds DRAW-8/pid 71 to DK2 across the affected writes.

| Target | Sufficient groups | BM25 / E5 / fused ranks | Action-only probe ranks |
| --- | --- | --- | --- |
| T1486 Data Encrypted for Impact | [['E1.1', 'E2.1', 'E3.1']] | [6, 130, 30] | [3, 11, 3] |

| Pass · arm | References in display order | Selected ID → citations and status | Missing by sufficient alternative | Outcome |
| --- | --- | --- | --- | --- |
| 1 · hybrid192_k5 | T1027.013, T1563, T1564.012, T1564.011, T1553.001 | T1027.013 → E2.1 (unkeyed)<br>T1563 → E1.1 (unkeyed)<br>T1564.011 → E2.1 (unkeyed) | {'T1486': [['E1.1', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 1 · bm25_k5 | T1027.013, T1564.013, T1608.004, T1539, T1036.009 | T1027.013 → E2.1 (unkeyed)<br>T1608.004 → E2.1 (unkeyed)<br>T1036.009 → E3.1 (unkeyed) | {'T1486': [['E1.1', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 2 · bm25_k5 | T1027.013, T1564.013, T1608.004, T1539, T1036.009 | T1027.013 → E2.1 (unkeyed)<br>T1608.004 → E2.1 (unkeyed)<br>T1036.009 → E3.1 (unkeyed) | {'T1486': [['E1.1', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |
| 2 · hybrid192_k5 | T1027.013, T1563, T1564.012, T1564.011, T1553.001 | T1027.013 → E2.1 (unkeyed)<br>T1563 → E1.1 (unkeyed)<br>T1564.011 → E2.1 (unkeyed) | {'T1486': [['E1.1', 'E2.1', 'E3.1']]} | expected_reference_absent, extra_technique, citation_without_keyed_support |

Raw response changed between passes for neither arm.
