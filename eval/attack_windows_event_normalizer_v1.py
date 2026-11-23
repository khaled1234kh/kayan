"""Deterministic parsing of saved Windows Security Event XML, offline."""
import calendar
from dataclasses import dataclass
from datetime import datetime
import re
from xml.etree import ElementTree
from xml.parsers import expat

NS = "http://schemas.microsoft.com/win/2004/08/events/event"
CLEAR_NS = "http://manifests.microsoft.com/win/2004/08/windows/eventlog"
MAX_BYTES = 65536
MAX_DEPTH = 12
NS_PER_SECOND = 1_000_000_000
PROFILES = {
    (1102, 0): ("Microsoft-Windows-Eventlog", "{fc65ddd8-d6ef-4962-83d5-6e5cfe9ce148}"),
    (4624, 2): ("Microsoft-Windows-Security-Auditing", "{54849625-5478-4994-a5ba-3e3b0328c30d}"),
}
UTC = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]{1,9}))?Z")
SID_DECIMAL = re.compile(r"0|[1-9][0-9]{0,9}")
SID_HEX_AUTHORITY = re.compile(r"0x[0-9a-fA-F]{12}")
UINT32_LIMIT = 1 << 32


class UnsupportedProfile(ValueError):
    """The original may be retained without normalized evidence."""


def parse_xml(raw):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("invalid XML size")
    source = raw.decode("utf-8")
    parser = expat.ParserCreate(namespace_separator=" ")
    depth = 0

    def start(_name, _attrs):
        nonlocal depth
        depth += 1
        if depth > MAX_DEPTH:
            raise ValueError("XML depth limit")

    def end(_name):
        nonlocal depth
        depth -= 1

    def reject(*_args):
        raise ValueError("unsafe XML construct")

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        parser.Parse(source, True)
        return ElementTree.fromstring(source)
    except (expat.ExpatError, ElementTree.ParseError) as exc:
        raise ValueError("malformed XML") from exc


def qname(namespace, name):
    return f"{{{namespace}}}{name}"


def resolve_xml(root, path, attribute=None):
    """Resolve a unique namespace-aware path, optionally selecting named Data."""
    node = root
    for namespace, name, data_name in path:
        matches = node.findall(qname(namespace, name))
        if data_name is not None:
            matches = [entry for entry in matches if entry.get("Name") == data_name]
        if len(matches) != 1:
            raise ValueError(f"missing or duplicate XML field: {name}")
        node = matches[0]
    if attribute is not None and attribute in node.attrib:
        return node.attrib[attribute]
    if attribute is None and not len(node) and node.text and node.text.strip():
        return node.text
    raise ValueError("missing or non-scalar XML value")


def utc_ns(text):
    match = UTC.fullmatch(text)
    if match is None:
        raise ValueError("expected UTC timestamp with up to nine fractional digits")
    second, fraction = match.groups()
    whole = calendar.timegm(datetime.fromisoformat(second).timetuple())
    fraction = fraction or ""
    return whole * NS_PER_SECOND + int(fraction.ljust(9, "0")), 10 ** (9 - len(fraction))


def _sid_key(raw):
    parts = raw.split("-")
    if not 4 <= len(parts) <= 18 or parts[:2] != ["S", "1"]:
        return None
    authority, *subauthorities = parts[2:]
    if SID_DECIMAL.fullmatch(authority) and int(authority) < UINT32_LIMIT:
        authority_key = authority
    elif SID_HEX_AUTHORITY.fullmatch(authority) and int(authority, 16) >= UINT32_LIMIT:
        authority_key = "0x" + authority[2:].upper()
    else:
        return None
    if any(not SID_DECIMAL.fullmatch(part) or int(part) >= UINT32_LIMIT for part in subauthorities):
        return None
    return "-".join(("S", "1", authority_key, *subauthorities))


def normalize(raw):
    root = parse_xml(raw)
    if root.tag != qname(NS, "Event"):
        raise ValueError("unexpected event namespace")
    fields, locators = {}, {}

    def read(key, path, attribute=None):
        value = resolve_xml(root, path, attribute)
        fields[key] = value
        locators[key] = {"path": path, "attribute": attribute}
        return value

    system = [(NS, "System", None)]
    for key, name in (("event_id", "EventID"), ("version", "Version"), ("channel", "Channel"),
                      ("computer", "Computer"), ("record_number", "EventRecordID")):
        read(key, [*system, (NS, name, None)])
    event_id, version = (int(fields[key]) if re.fullmatch(r"[0-9]{1,10}", fields[key]) else -1
                         for key in ("event_id", "version"))
    if fields["channel"] != "Security" or event_id < 0 or version < 0:
        raise ValueError("invalid security event header")
    if (event_id, version) not in PROFILES:
        raise UnsupportedProfile("unsupported event/profile version")
    if not re.fullmatch(r"[0-9]{1,20}", fields["record_number"]):
        raise ValueError("invalid native record number")
    provider = [*system, (NS, "Provider", None)]
    name = read("provider", provider, "Name")
    guid = read("provider_guid", provider, "Guid")
    if (name, guid.casefold()) != PROFILES[event_id, version]:
        raise ValueError("unexpected provider identity")
    raw_time = read("time", [*system, (NS, "TimeCreated", None)], "SystemTime")
    stamp, precision = utc_ns(raw_time)
    prefix = "Subject" if event_id == 1102 else "Target"
    for key, suffix in (("sid", "UserSid"), ("name", "UserName"), ("domain", "DomainName"),
                        ("logon_id", "LogonId")):
        tag = prefix + suffix
        path = ([(NS, "UserData", None), (CLEAR_NS, "LogFileCleared", None), (CLEAR_NS, tag, None)]
                if event_id == 1102 else [(NS, "EventData", None), (NS, "Data", tag)])
        read(key, path)
    if event_id == 4624:
        logon_type = read("logon_type", [(NS, "EventData", None), (NS, "Data", "LogonType")])
        if not re.fullmatch(r"[0-9]{1,10}", logon_type) or int(logon_type) >= 2**32:
            raise ValueError("invalid logon type")
    diagnostics = []
    sid = _sid_key(fields["sid"])
    if not sid or sid == "S-1-0-0":
        sid = None
        diagnostics.append("unresolved_sid")
    token = fields["logon_id"]
    logon_id = int(token, 16) if re.fullmatch(r"0[xX][0-9a-fA-F]{1,16}", token) else None
    if not logon_id:
        diagnostics.append("unresolved_logon_id")
    return {
        "profile": f"windows-security/{event_id}/{version}", "original_fields": fields,
        "locators": locators, "reported_at_ns": stamp, "precision_ns": precision, "clock_basis": "UTC",
        "sid": sid, "logon_id": logon_id, "diagnostics": diagnostics,
        "reported_outcome": "completed_clear" if event_id == 1102 else "successful_logon",
    }


def normalize_observation(raw):
    """Retain an unsupported profile as an observation with a diagnostic."""
    try:
        return {"state": "normalized", "fields": normalize(raw)}
    except UnsupportedProfile as exc:
        return {"state": "unsupported", "reason": str(exc)}


@dataclass(frozen=True)
class SessionObservation:
    """Trusted catalogue scope plus a source observation. Bounds are externally reviewed."""
    record_ref: str
    case_id: str
    tenant: str
    asset: str
    authority: str
    generation: str | None
    generation_window_ns: tuple[int, int] | None
    clock_error_ns: int | None
    observation: dict


def _interval(scoped):
    if (not all((scoped.case_id, scoped.tenant, scoped.asset, scoped.authority, scoped.generation))
            or scoped.generation_window_ns is None
            or scoped.clock_error_ns is None or scoped.clock_error_ns < 0):
        return None
    start = scoped.observation["reported_at_ns"] - scoped.clock_error_ns
    end = (scoped.observation["reported_at_ns"] + scoped.observation["precision_ns"]
           + scoped.clock_error_ns)
    left, right = scoped.generation_window_ns
    return (start, end) if left <= start < end <= right else None


def session_candidate(clear, logons, *, window_ns):
    """Identify one possible same-scope logon. A candidate carries no review authority."""
    if clear.observation["profile"] != "windows-security/1102/0" or window_ns <= 0:
        raise ValueError("expected an audit clear and a positive join window")
    target = clear.observation
    interval = _interval(clear)
    if interval is None or not target["sid"] or not target["logon_id"]:
        return {"state": "unresolved", "reason": "clear_scope_or_identity_unresolved"}
    scope = (clear.case_id, clear.tenant, clear.asset, clear.authority)
    candidates = []
    for logon in logons:
        obs = logon.observation
        if (obs["profile"] != "windows-security/4624/2"
                or (logon.case_id, logon.tenant, logon.asset, logon.authority) != scope
                or (obs["sid"] is not None and obs["sid"] != target["sid"])
                or (obs["logon_id"] and obs["logon_id"] != target["logon_id"])
                or logon.generation not in (None, clear.generation)):
            continue
        earlier = _interval(logon)
        if earlier is None or logon.generation_window_ns != clear.generation_window_ns:
            return {"state": "unresolved", "reason": "matching_logon_scope_unresolved"}
        if earlier[0] >= interval[1] or interval[0] - earlier[1] >= window_ns:
            continue
        if earlier[1] > interval[0] or interval[1] - earlier[0] > window_ns:
            return {"state": "unresolved", "reason": "event_order_or_window_uncertain"}
        if obs["sid"] is None or not obs["logon_id"]:
            return {"state": "unresolved", "reason": "plausible_logon_identity_unresolved"}
        # Neither a matching record_ref nor matching normalized fields proves
        # that two inputs describe the same original source record.
        candidates.append(logon.record_ref)
    if len(candidates) != 1:
        return {"state": "unresolved", "reason": "ambiguous_or_missing_logon"}
    return {"state": "candidate", "record_ref": candidates[0]}
