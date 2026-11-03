"""Versioned, authored scenario rules over descriptive text, entirely offline.

These transparent applicability rules are intentionally narrower than general
security analysis. They neither infer missing controls nor measure actual risk.
Framework references come from the project's existing pinned local index.
"""
import re


RULES = [
    dict(id='vendor_remote_access', title='Review vendor access to internal systems', reference='T1133',
         groups={'remote access': [r'\bVPNs?\b', r'\bremote\s+access\b'], 'external operators': [r'\bvendors?\b', r'\bthird.party\b', r'\bcontractors?\b', r'\bremote\s+workers?\b']},
         gaps=[r'access\s+reviews?[^.;\n]{0,55}(?:infrequent|missing|not\s+documented)', r'shared[^.;\n]{0,25}accounts?'],
         consequence='A compromised or stale external account could provide an entry path to the internal systems reachable through that connection.',
         why='External Remote Services describes remote entry paths such as VPN access; the description explicitly names both the connection and its external users.',
         assumptions='Whether MFA, expiry, least privilege and account reviews actually work has not been checked.',
         controls=['Inventory the described vendor VPN identities and their permitted destinations; assign a named owner and expiry to each external account.',
                   'Use individual accounts and MFA where supported; remove stale access through an approved access review.',
                   'Restrict vendor connections to the required destinations in the supplied network description, log sessions and review privileged changes.'],
         validation=['Review the vendor-to-destination access matrix with the system owner.', 'Confirm account expiry and MFA enforcement using an approved control review; no live test is performed here.']),
    dict(id='recovery_readiness', title='Check recovery of the described business data', reference='T1490',
         groups={'backups': [r'\bbackups?\b'], 'recovery gap': [r'\brestor(?:e|ation)\s+test(?:s|ing)?[^.;\n]{0,45}(?:undocumented|not\s+documented|untested|inconsistent)', r'\b(?:untested|undocumented)\s+backups?\b']},
         gaps=[r'undocumented|untested|not\s+documented|inconsistent'],
         consequence='If recovery copies or recovery permissions are compromised, the organization could be unable to restore the data needed for operations.',
         why='Inhibit System Recovery describes adversary interference with recovery. The description names backups and a recovery-validation gap; it does not prove that backups are vulnerable.',
         assumptions='Backup isolation, retention, integrity, recovery objectives and restore success remain unknown.',
         controls=['Identify the specific datasets in the description that must be restored and agree recovery objectives with their owners.',
                   'Separate backup administration from production identities; review deletion permissions and protected or offline recovery copies where appropriate.',
                   'Run and document an approved restore exercise for the described data, including integrity checks, dependencies and the measured recovery time.'],
         validation=['Obtain the restore procedure and a dated restore-test record.', 'Confirm that the restored sample is usable; this plan does not establish recovery capability.']),
    dict(id='api_object_access', title='Review authorization on customer and record APIs', reference='A01:2025',
         groups={'application interfaces': [r'\bREST\s+APIs?\b', r'\bAPIs?\b', r'\bcustomer\s+portal\b'], 'records or accounts': [r'\border\s+(?:tracking|histor\w*)\b', r'\bcustomer\s+(?:information|accounts?|records?)\b', r'\bpatient.records?\b', r'\btenant\w*\b', r'\brefund\w*\b']},
         gaps=[r'(?:authorization|access\s+control)[^.;\n]{0,35}(?:missing|broken|not\s+checked)'],
         consequence='If record ownership and operation-level permissions are not enforced server-side, a user or integration could read or change another account\'s records.',
         why='Broken Access Control applies to object and operation authorization. Named interfaces and record/account workflows make this a review hypothesis, not proof of an authorization defect.',
         assumptions='Actual ownership checks, tenant isolation and integration permissions are unknown.',
         controls=['Map each described API operation to the record owner, user role and permitted integration identity.',
                   'Enforce server-side object and operation authorization on record lookup and state changes; derive account scope from the authenticated identity.',
                   'Restrict third-party integration permissions and review which customer or operational fields each integration receives.'],
         validation=['Review an API-to-role/record ownership matrix.', 'Prepare authorized cross-account and integration-permission tests for a later assessment; none are executed by Phase 1.']),
    dict(id='web_input_processing', title='Review input handling at the application/database boundary', reference='A05:2025',
         groups={'application input': [r'\bpublic\s+(?:web\s+)?application\b', r'\bweb\s+application\b', r'\bREST\s+APIs?\b', r'\bAPIs?\b'], 'database or input path': [r'\bSQL\b', r'\brelational\s+database\b', r'\b(?:search|login|registration|forms?)\b']},
         gaps=[r'\bSQL\s+injection\b'],
         consequence='If untrusted input crosses into query or rendered-content construction unsafely, an application user could access unintended data or inject active content.',
         why='Injection concerns interpretation of untrusted input. The description supplies an application-input path and a database or form boundary to review.',
         assumptions='No injection vulnerability, query construction defect or browser execution has been verified.',
         controls=['Trace the described login, search or API input paths to their query and output boundaries; identify the owning development team.',
                   'Use parameterized queries for the described SQL or relational data path, server-side request validation and least-privilege application database identities.',
                   'Apply contextual output encoding where user-controlled content is rendered, and add regression checks for the relevant input paths.'],
         validation=['Review representative query construction and output templates with the application owner.', 'Define an authorized follow-up test for each named input boundary; no payloads or requests are sent here.']),
    dict(id='cloud_object_access', title='Review access to cloud-held objects and backups', reference='T1530',
         groups={'cloud objects': [r'\bcloud\s+object\s+storage\b', r'\bS3\b', r'\b(?:storage\s+)?buckets?\b', r'\bblob\s+storage\b'], 'stored assets': [r'\bimages?\b', r'\bbackups?\b', r'\bdocuments?\b', r'\brecords?\b']},
         gaps=[r'\bpublic\s+buckets?\b', r'\bbroad\s+permissions\b'],
         consequence='If object permissions or link-sharing settings are broader than intended, sensitive objects or recovery copies could be exposed to unintended readers.',
         why='Data from Cloud Storage concerns collection from cloud storage services. The description names both an object-storage service and assets held there.',
         assumptions='No public bucket, exposed object or excessive permission has been verified.',
         controls=['Separate public product or marketing objects from sensitive records and recovery copies; record the intended reader for each collection.',
                   'Review bucket/container policies, service identities and time-limited sharing links against that classification.',
                   'Review object access logging, encryption/key access and lifecycle rules with the storage owner.'],
         validation=['Review a storage-to-data-classification/access matrix.', 'Inspect approved policy exports and sample access-review evidence; Phase 1 does not query storage services.']),
    dict(id='shared_identity', title='Replace shared access to the described business application', reference='A07:2025',
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
         groups={'unsupported components': [r'\blegacy\b', r'\bunsupported\b'], 'device or software estate': [r'\bdevices?\b', r'\bservers?\b', r'\bsoftware\b', r'\bPLCs?\b']},
         gaps=[r'\bunsupported\b', r'\bcannot\s+be\s+patched\b'],
         consequence='Unsupported components may retain unresolved weaknesses; broad access or an unplanned update could also threaten service availability.',
         why='Software Supply Chain Failures includes unmaintained or non-updateable components in the pinned reference. The description explicitly names legacy or unsupported devices, supporting a lifecycle review rather than an exploit claim.',
         assumptions='No vulnerable version or exploitable component has been identified by this offline plan.',
         controls=['Inventory the named legacy devices, owners, supported versions and vendor maintenance constraints.',
                   'Agree patch, replacement or compensating-control options with the responsible operations team; do not perform unplanned updates.',
                   'Restrict unnecessary access and monitor approved management paths while lifecycle remediation is planned.'],
         validation=['Review the component inventory and vendor-support evidence.', 'Document the accepted maintenance or replacement plan and its availability constraints.']),
]


def _matches(context, patterns, signal):
    result=[]
    for field, text in context.items():
        if field in ('company_size','departments'):
            continue  # Organizational labels alone cannot establish technical applicability.
        for pattern in patterns:
            for match in re.finditer(pattern,text,re.I):
                prefix=text[max(0,match.start()-70):match.start()]
                prefix=re.split(r'[.;\n]|\bbut\b|\bhowever\b',prefix,flags=re.I)[-1]
                if re.search(r"\b(?:no|without|never|not|neither)\b(?:\W+\w+){0,5}\W*$",prefix,re.I):
                    continue
                start=max(text.rfind('.',0,match.start())+1,text.rfind('\n',0,match.start())+1)
                end=text.find('.',match.end())
                end=len(text) if end<0 else end+1
                if end-start>260:
                    start=max(start,match.start()-65);end=min(end,start+260)
                result.append({'field':field,'signal':signal,'matched_text':match.group(),
                    'start':start,'end':end,'excerpt':text[start:end]})
                break
            if result and result[-1]['field']==field:
                break
    return result


def contextual_candidates(context,index):
    refs={entry['id']:entry for entry in index.entries}
    candidates=[]
    for rule in RULES:
        groups={signal:_matches(context,patterns,signal) for signal,patterns in rule['groups'].items()}
        if not all(groups.values()) or rule['reference'] not in refs:
            continue
        # No generic account hypothesis duplicates a more specific vendor-account scenario.
        if rule['id']=='shared_identity' and any(c['scenario_id']=='vendor_remote_access' for c in candidates):
            continue
        evidence=[items[0] for items in groups.values()]
        gaps=_matches(context,rule['gaps'],'stated control gap')
        if gaps and not any(g['excerpt']==e['excerpt'] for g in gaps for e in evidence):evidence.append(gaps[0])
        score=round(len(groups)+0.1*len({e['field'] for e in evidence})+(2 if gaps else 0),2)
        reference=refs[rule['reference']]
        candidates.append({'scenario_id':rule['id'],'title':rule['title'],
            'hypothesis':rule['consequence'],'why_relevant':rule['why'],
            'assumptions':rule['assumptions'],'assets':list(groups),'context_evidence':evidence,
            'relevance_score':score,'relevance_basis':'Matched required technical signals'+('; a related control gap is explicitly described' if gaps else '; controls remain unverified'),
            'severity':'not_assessed','impact':'not_assessed','likelihood':'not_assessed','mitigation_urgency':'not_assessed',
            'reference':{key:reference[key] for key in ('id','framework','name','source_url','description')},
            'control_actions':rule['controls'],'validation_steps':rule['validation']})
    return sorted(candidates,key=lambda c:(-c['relevance_score'],c['scenario_id']))
