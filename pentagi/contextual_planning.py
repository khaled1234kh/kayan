"""Versioned, authored scenario rules over descriptive text, entirely offline.

These transparent applicability rules are intentionally narrower than general
security analysis. They neither infer missing controls nor measure actual risk.
Framework references come from the project's existing pinned local index.
"""
import re


RECOVERY_GAP = (
    r'\brestor(?:e|ation)\s+test(?:s|ing)?\s+(?:(?:is|are|was|were|remains?)\s+)?'
    r'(?:undocumented|not\s+documented|untested|inconsistent)\b',
    r'\b(?:untested|undocumented)\s+backups?\b',
    r'\b(?:have|has)\s+not\s+(?:checked|tested|verified)\s+(?:that|whether)\s+'
    r'(?:it|they|the\s+(?:data|system|copies|backups))\s+can\s+be\s+restored\b',
)
SUPPORT_GAP = (
    r'\bunsupported\b', r'\bend[- ]of[- ]life\b',
    r'\b(?:out\s+of\s+support|no\s+longer\s+supported|cannot\s+be\s+patched)\b',
)
EXTERNAL_OPERATOR = r'\b(?:vendors?|third[- ]part(?:y|ies)|contractors?)\b'
REMOTE_PATH = r'\b(?:VPNs?|remote\s+access)\b'
ACCESS_RECIPIENT = rf'(?:(?:the|external|approved)\s+)*{EXTERNAL_OPERATOR}'
PATH_WORDS = r"(?:(?!\b(?:and|or|who|which|where|staff|employees?|not|without|never)\b)[\w'-]+\s+){0,10}"
VENDOR_ACCESS_LINK = (
    rf'{EXTERNAL_OPERATOR}\s+(?:and\s+(?:internal\s+)?(?:staff|employees)\s+)?'
    rf'(?:uses?|connects?|access(?:es)?)\s+{PATH_WORDS}{REMOTE_PATH}',
    rf'{EXTERNAL_OPERATOR}\s+(?:(?:support|maintenance)\s+)?{REMOTE_PATH}',
    rf'{REMOTE_PATH}\s+(?:(?:is|are)\s+)?(?:used\s+by|provided\s+(?:for|to)|'
    rf'lets?|allows?|permits?|for|to)\s+{ACCESS_RECIPIENT}',
)


RULES = [
    dict(id='vendor_remote_access', title='Review vendor access to internal systems', reference='T1133',
         same_clause=True,
         groups={'remote access': [REMOTE_PATH], 'external operators': [EXTERNAL_OPERATOR]},
         relationship=VENDOR_ACCESS_LINK,
         gaps=[r'access\s+reviews?[^.;\n]{0,55}(?:infrequent|missing|not\s+documented)', r'shared[^.;\n]{0,25}accounts?'],
         consequence='A compromised or stale external account could provide an entry path to the internal systems reachable through that connection.',
         why='External Remote Services describes remote entry paths such as VPN access; the description explicitly names both the connection and its external users.',
         assumptions='Whether MFA, expiry, least privilege and account reviews actually work has not been checked.',
         controls=['Inventory external identities on the described access path and their permitted destinations; assign a named owner and expiry to each external account.',
                   'Use individual accounts and MFA where supported; remove stale access through an approved access review.',
                   'Restrict vendor connections to the required destinations in the supplied network description, log sessions and review privileged changes.'],
         validation=['Review the vendor-to-destination access matrix with the system owner.', 'Confirm account expiry and MFA enforcement using an approved control review; no live test is performed here.']),
    dict(id='recovery_readiness', title='Check recovery of the described business data', reference='T1490',
         groups={'backups': [r'\bbackups?\b', r'\bbacked\s+up\b'], 'recovery gap': RECOVERY_GAP},
         gaps=RECOVERY_GAP,
         consequence='If recovery copies or recovery permissions are compromised, the organization could be unable to restore the data needed for operations.',
         why='Inhibit System Recovery describes adversary interference with recovery. The description names backups and a recovery-validation gap; it does not prove that backups are vulnerable.',
         assumptions='Backup isolation, retention, integrity, recovery objectives and restore success remain unknown.',
         controls=['Identify the specific datasets in the description that must be restored and agree recovery objectives with their owners.',
                   'Separate backup administration from production identities; review deletion permissions and protected or offline recovery copies where appropriate.',
                   'Run and document an approved restore exercise for the described data, including integrity checks, dependencies and the measured recovery time.'],
         validation=['Obtain the restore procedure and a dated restore-test record.', 'Confirm that the restored sample is usable; this plan does not establish recovery capability.']),
    dict(id='api_object_access', title='Review authorization on customer and record APIs', reference='A01:2025',
         same_clause=True,
         groups={'application interfaces': [r'\bREST\s+APIs?\b', r'\bAPIs?\b', r'\bcustomer\s+portal\b'], 'records or accounts': [r'\border\s+(?:tracking|histor\w*)\b', r'\bcustomer\s+(?:information|accounts?|records?)\b', r'\bpatient.records?\b', r'\btenant\w*\b', r'\brefund\w*\b']},
         gaps=[r'(?:authorization|access\s+control)[^.;\n]{0,35}(?:missing|broken|not\s+checked)'],
         consequence='If record ownership and operation-level permissions are not enforced server-side, a user or integration could read or change another account\'s records.',
         why='Broken Access Control applies to object and operation authorization. Named interfaces and record/account workflows make this a review hypothesis, not proof of an authorization defect.',
         assumptions='Actual ownership checks, tenant isolation and integration permissions are unknown.',
         controls=['Map each described API operation to the record owner, user role and permitted integration identity.',
                   'Enforce server-side object and operation authorization on record lookup and state changes; derive account scope from the authenticated identity.',
                   'Restrict third-party integration permissions and review which customer or operational fields each integration receives.'],
         validation=['Review an API-to-role/record ownership matrix.', 'Prepare authorized cross-account and integration-permission tests for a later assessment; none are executed by Phase 1.']),
    dict(id='web_input_processing', title='Review input handling in the described application', reference='A05:2025',
         same_clause=True,
         groups={'application input': [r'\bpublic\s+(?:web\s+)?application\b', r'\bweb\s+application\b', r'\bREST\s+APIs?\b', r'\bAPIs?\b'], 'database or input path': [r'\bSQL\b', r'\brelational\s+database\b', r'\b(?:search|login|registration|forms?)\b']},
         gaps=[r'\bSQL\s+injection\b'],
         consequence='If untrusted input crosses into query or rendered-content construction unsafely, an application user could access unintended data or inject active content.',
         why='Injection concerns interpretation of untrusted input. The description supplies an application-input path and a database or form boundary to review.',
         assumptions='No injection vulnerability, query construction defect or browser execution has been verified.',
         controls=['Trace the described login, search or API input paths to their query and output boundaries; identify the owning development team.',
                   'Apply server-side request validation to the described path. Where it reaches a relational database, use parameterized queries and least-privilege database identities.',
                   'Apply contextual output encoding where user-controlled content is rendered, and add regression checks for the relevant input paths.'],
         validation=['Review representative query construction and output templates with the application owner.', 'Define an authorized follow-up test for each named input boundary; no payloads or requests are sent here.']),
    dict(id='cloud_object_access', title='Review access to cloud-held objects and backups', reference='T1530',
         same_clause=True,
         groups={'cloud objects': [r'\bcloud\s+object\s+storage\b', r'\bS3\b', r'\bstorage\s+buckets?\b', r'\bblob\s+storage\b'], 'stored assets': [r'\bimages?\b', r'\bbackups?\b', r'\bdocuments?\b', r'\brecords?\b']},
         gaps=[r'\bpublic\s+buckets?\b', r'\bbroad\s+permissions\b'],
         consequence='If object permissions or link-sharing settings are broader than intended, sensitive objects or recovery copies could be exposed to unintended readers.',
         why='Data from Cloud Storage concerns collection from cloud storage services. The description names both an object-storage service and assets held there.',
         assumptions='No public bucket, exposed object or excessive permission has been verified.',
         controls=['Separate public product or marketing objects from sensitive records and recovery copies; record the intended reader for each collection.',
                   'Review bucket/container policies, service identities and time-limited sharing links against that classification.',
                   'Review object access logging, encryption/key access and lifecycle rules with the storage owner.'],
         validation=['Review a storage-to-data-classification/access matrix.', 'Inspect approved policy exports and sample access-review evidence; Phase 1 does not query storage services.']),
    dict(id='shared_identity', title='Replace shared access to the described business application', reference='A07:2025',
         same_clause=True,
         groups={'business identities': [r'\blogins?\b', r'\baccounts?\b'], 'shared identity gap': [r'\bshared\s+(?:\w+\s+){0,2}(?:accounts?|logins?)\b', r'\bshare\s+(?:\w+\s+){0,2}(?:accounts?|logins?)\b']},
         gaps=[r'\bshare(?:d)?\s+(?:\w+\s+){0,2}(?:accounts?|logins?)\b'],
         consequence='A shared identity can prevent reliable attribution and may leave former or unrelated users able to access business records.',
         why='Authentication Failures is relevant because the description explicitly identifies shared authentication, not merely a generic use of accounts.',
         assumptions='The actual account lifecycle and application role enforcement have not been reviewed.',
         controls=['Identify each use of a shared login in the described application and assign individual user identities with role-appropriate record access.',
                   'Define joiner/leaver access changes and remove shared credentials through a controlled transition with the application owner.',
                   'Review MFA support, session handling and logs that attribute sensitive record access to an individual.'],
         validation=['Review the account-to-person/role mapping.', 'Check a sample leaver record and an attributable access-log entry through an approved review.']),
    dict(id='industrial_segmentation', title='Review office-to-production network boundaries', reference='T1021',
         same_clause=True,
         groups={'production devices': [r'\bindustrial\s+devices?\b', r'\bPLCs?\b', r'\bproduction\s+lines?\b', r'\bIoT\s+devices?\b'], 'shared network': [r'\bflat\s+network\b', r'\bshare\s+(?:a\s+)?(?:flat\s+)?network\b', r'\bnot\s+segmented\b']},
         gaps=[r'\bflat\s+network\b', r'\bnot\s+segmented\b'],
         consequence='If a compromised office or maintenance endpoint can use permissive remote-service paths, compromise could spread into production devices.',
         why='Remote Services describes potential lateral movement paths. The description names production devices and a shared network; reachable remote services remain an explicit assumption.',
         assumptions='No remote-service reachability or attack path into production has been tested.',
         controls=['Map permitted office, maintenance and vendor connections to the named production-device zones.',
                   'Review segmentation rules and restrict management paths to approved maintenance systems and identities.',
                   'Coordinate logging and any boundary changes with plant operations and equipment owners to protect availability.'],
         validation=['Review an approved zone/conduit and maintenance-access diagram.', 'Plan any connectivity validation with operations; Phase 1 performs no industrial scans.']),
    dict(id='legacy_components', title='Manage support limits on the described legacy devices', reference='A03:2025',
         same_clause=True,
         groups={'support gap': SUPPORT_GAP, 'device or software estate': [r'\bdevices?\b', r'\bservers?\b', r'\bsoftware\b', r'\bPLCs?\b']},
         gaps=SUPPORT_GAP,
         consequence='Unsupported components may retain unresolved weaknesses; broad access or an unplanned update could also threaten service availability.',
         why='The pinned Software Supply Chain Failures reference includes unmaintained or non-updateable components. The description names a component and a support or patching gap that warrants lifecycle review.',
         assumptions='No vulnerable version or exploitable component has been identified by this offline plan.',
         controls=['Inventory the named legacy devices, owners, supported versions and vendor maintenance constraints.',
                   'Agree patch, replacement or compensating-control options with the responsible operations team; do not perform unplanned updates.',
                   'Restrict unnecessary access and monitor approved management paths while lifecycle remediation is planned.'],
         validation=['Review the component inventory and vendor-support evidence.', 'Document the accepted maintenance or replacement plan and its availability constraints.']),
]


CLAUSE_BREAK = re.compile(r'[.!?;\n]+|\b(?:but|however|although|whereas)\b', re.I)
ABSENCE_BEFORE = re.compile(
    r'\b(?:no(?!\s+(?:more|fewer)\s+than)|not(?!\s+(?:only|just)\b)|without|never|neither|no\s+longer)\b'
    r'(?:\W+\w+){0,7}\W*$', re.I,
)
NONCURRENT = re.compile(
    r'\b(?:previously|formerly|used\s+to|considering|propos(?:e|es|ed|ing)|'
    r'plan(?:s|ned|ning)?\s+to|intend(?:s|ed)?\s+to|will\s+(?:add|deploy|use|introduce))\b', re.I,
)
ABSENCE_AFTER = re.compile(
    r'^\s*(?:(?:is|are|was|were|has\s+been|have\s+been)\s+)?'
    r'(?:employee(?:s)?\s+only|for\s+(?:employees?|staff)\s+only|'
    r'(?:no\s+longer|not)\s+(?:in\s+use|used|operated|provided|available|deployed|enabled)|'
    r'retired|decommissioned|discontinued|disabled|prohibited|planned|under\s+consideration)\b',
    re.I,
)


def _technical_clauses(context):
    for field, text in context.items():
        if field in ('company_size', 'departments'):
            continue
        start = 0
        for separator in CLAUSE_BREAK.finditer(text):
            if separator.start() > start and '?' not in separator.group():
                yield (field, start), text[start:separator.start()]
            start = separator.end()
        if start < len(text):
            yield (field, start), text[start:]


def _matches(clauses, patterns, signal):
    matches = {}
    pattern = re.compile('|'.join(f'(?:{part})' for part in patterns), re.I)
    for (field, offset), clause in clauses.items():
        if NONCURRENT.search(clause):
            continue
        for match in pattern.finditer(clause):
            if (match.end() - match.start() > 260
                    or ABSENCE_BEFORE.search(clause[:match.start()])
                    or ABSENCE_AFTER.match(clause[match.end():])):
                continue
            start = max(0, match.start() - 65, match.end() - 260) if len(clause) > 260 else 0
            end = min(len(clause), start + 260)
            matches[(field, offset)] = {
                'field': field, 'signal': signal, 'matched_text': match.group(),
                'start': offset + start, 'end': offset + end, 'excerpt': clause[start:end],
            }
            break
    return matches


def contextual_candidates(context,index):
    refs={entry['id']:entry for entry in index.entries}
    clauses = dict(_technical_clauses(context))
    vendor_access_clauses = set()
    candidates=[]
    for rule in RULES:
        groups = [_matches(clauses, patterns, signal) for signal, patterns in rule['groups'].items()]
        if not all(groups) or rule['reference'] not in refs:
            continue
        relationship = rule.get('relationship')
        linked = _matches(clauses, relationship, 'vendor-to-remote access link') if relationship else None
        if rule.get('same_clause'):
            shared_clauses = set.intersection(*(set(group) for group in groups))
            if linked is not None:
                shared_clauses &= linked.keys()
            if rule['id'] == 'shared_identity':
                # Suppress duplicate account cues only where external access is also supported.
                shared_clauses -= vendor_access_clauses
            if not shared_clauses:
                continue
            if rule['id'] == 'vendor_remote_access':
                vendor_access_clauses = shared_clauses
            evidence_scopes = [next(scope for scope in clauses if scope in shared_clauses)] * len(groups)
        else:
            evidence_scopes = [next(iter(group)) for group in groups]
        evidence = [group[scope] for group, scope in zip(groups, evidence_scopes)]
        if linked is not None:
            evidence.append(linked[evidence_scopes[0]])
        gaps = _matches(clauses, rule['gaps'], 'stated control gap')
        # A separate vendor-access review sentence can qualify when it names the external party.
        gap = next((item for scope, item in gaps.items() if scope in evidence_scopes
                    or (rule['id'] == 'vendor_remote_access'
                        and scope[0] == evidence_scopes[0][0]
                        and re.search(r'\b(?:vendors?|contractors?|third.party)\b', clauses[scope], re.I))), None)
        if gap:
            evidence.append(gap)
        score=round(len(groups)+0.1*len({e['field'] for e in evidence})+(2 if gap else 0),2)
        reference=refs[rule['reference']]
        candidates.append({'scenario_id':rule['id'],'title':rule['title'],
            'hypothesis':rule['consequence'],'why_relevant':rule['why'],
            'assumptions':rule['assumptions'],'assets':list(rule['groups']),'context_evidence':evidence,
            'relevance_score':score,'relevance_basis':'Matched required technical signals'+('; a related control gap is explicitly described' if gap else '; controls remain unverified'),
            'severity':'not_assessed','impact':'not_assessed','likelihood':'not_assessed','mitigation_urgency':'not_assessed',
            'reference':{key:reference[key] for key in ('id','framework','name','source_url','description')},
            'control_actions':rule['controls'],'validation_steps':rule['validation']})
    return sorted(candidates,key=lambda c:(-c['relevance_score'],c['scenario_id']))
