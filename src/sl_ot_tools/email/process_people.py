#!/usr/bin/env python3
"""
process_people.py — Scan email exports for new/updated people signals.

Project-agnostic tool. All project-specific settings (domains, org chart
path, domain-to-org mapping, contractor patterns) live in config files
that are auto-discovered by convention:
  - _company/company_config.json  (domains, labels, patterns, hints)
  - _company/people_config.json   (org_chart, checkpoint, ignore_list paths)

Reads an email export (from read_email.sh), compares against an existing
org chart JSON, and produces a report of:
  - New people from domains of interest not yet in the org chart
  - Updated signals for known people (new subjects, correspondents)

Usage:
    python3 process_people.py <email_output_dir> [options]

    -c, --config PATH  Path to people_config.json (auto-discovered if omitted)
    --company-config   Path to company_config.json (auto-discovered if omitted)
    --org-chart PATH   Override org chart path from config
    --checkpoint PATH  Override checkpoint path from config
    --reprocess        Ignore checkpoint, reprocess all emails
    --domains LIST     Override domains (comma-separated)
    --output PATH      Path to write report (default: <email_output_dir>/people_report.json)
    --ignore-list PATH Override ignore list path from config
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

# --- Auto-discovery helpers ---

def _find_company_dir(start_path=None):
    """Walk up from start_path to find _company/ directory."""
    current = os.path.abspath(start_path or os.getcwd())
    for _ in range(20):
        candidate = os.path.join(current, "_company")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def _find_repo_root(start_path=None):
    """Walk up to find repo root (parent of _company/)."""
    company_dir = _find_company_dir(start_path)
    if company_dir:
        return os.path.dirname(company_dir)
    return None


# --- Signature extraction patterns ---

SIG_DELIMITERS = re.compile(
    r"^(?:--|__|===|---+|___+|Best\s+regards|Kind\s+regards|Regards|"
    r"Thanks|Thank\s+you|Cheers|Sincerely|Warm\s+regards|BR,|Best,)",
    re.IGNORECASE,
)

TITLE_PATTERNS = re.compile(
    r"(?:Chief|President|Vice\s+President|VP|SVP|EVP|"
    r"Senior\s+Director|Director|Sr\.?\s+Director|"
    r"Senior\s+Manager|Manager|Sr\.?\s+Manager|"
    r"Head\s+of|Lead|Principal|Staff|Architect|"
    r"Fellow|Distinguished|Engineer|Consultant|"
    r"Partner|Advisor|Analyst|Associate|Specialist|"
    r"Administrator|Coordinator|CTO|CIO|CFO|CEO|COO|CMO)",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?:Tel|Phone|Mobile|Cell|Office|Direct|Fax)[\s:]*[\+\d\(\)\-\.\s]{7,}",
    re.IGNORECASE,
)

EMAIL_REGEX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def load_json(path):
    """Load JSON with BOM-safe encoding (handles PowerShell UTF-8 BOM)."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_config(config_path=None, company_config_path=None):
    """Load config by merging company_config.json + people_config.json.

    If paths are not provided, auto-discovers them from _company/.
    """
    company_dir = _find_company_dir()

    # Load people_config
    if config_path is None and company_dir:
        config_path = os.path.join(company_dir, "people_config.json")

    defaults = {
        "domains": [],
        "domain_labels": {},
        "org_chart": "",
        "checkpoint": "",
        "ignore_list": "",
        "contractor_patterns": [r"^[a-z]+x\."],
        "location_hints": [],
    }

    cfg = dict(defaults)

    if config_path and os.path.exists(config_path):
        people_cfg = load_json(config_path)
        cfg_dir = os.path.dirname(os.path.abspath(config_path))
        for key in ("org_chart", "checkpoint", "ignore_list"):
            val = people_cfg.get(key, "")
            if val and not os.path.isabs(val):
                val = os.path.normpath(os.path.join(cfg_dir, val))
            if val:
                cfg[key] = val
    else:
        # Fallback: resolve from company_dir conventions
        if company_dir:
            cfg["org_chart"] = os.path.join(company_dir, "org_chart.json")
            cfg["checkpoint"] = os.path.join(company_dir, "people_checkpoint.json")
            cfg["ignore_list"] = os.path.join(company_dir, "people_ignore.json")

    # Load company_config for domains, labels, patterns, hints
    if company_config_path is None and company_dir:
        company_config_path = os.path.join(company_dir, "company_config.json")

    if company_config_path and os.path.exists(company_config_path):
        cc = load_json(company_config_path)
        if cc.get("domains"):
            cfg["domains"] = cc["domains"]
        if cc.get("domain_labels"):
            cfg["domain_labels"] = cc["domain_labels"]
        if cc.get("contractor_patterns"):
            cfg["contractor_patterns"] = cc["contractor_patterns"]
        if cc.get("location_hints"):
            cfg["location_hints"] = cc["location_hints"]
        if cc.get("skip_senders"):
            cfg["skip_senders"] = cc["skip_senders"]

    return cfg, config_path


def build_known_people(org_chart):
    """Build a lookup of known email addresses from the org chart."""
    known = {}

    def _extract_from_list(people_list, section_name):
        for person in people_list:
            email = (person.get("email") or "").strip().lower()
            if email:
                known[email] = {
                    "name": person.get("name", ""),
                    "section": section_name,
                    "title": person.get("title", ""),
                }

    for key in ("leadership", "people", "team", "contacts"):
        if key in org_chart and isinstance(org_chart[key], list):
            _extract_from_list(org_chart[key], key)

    def _walk_ecosystem(node, path="external_ecosystem"):
        if isinstance(node, dict):
            if "key_contacts" in node and isinstance(node["key_contacts"], list):
                _extract_from_list(node["key_contacts"], path)
            for k, v in node.items():
                if k == "key_contacts":
                    continue
                if isinstance(v, (dict, list)):
                    _walk_ecosystem(v, f"{path}.{k}")
        elif isinstance(node, list):
            _extract_from_list(node, path)

    if "external_ecosystem" in org_chart:
        _walk_ecosystem(org_chart["external_ecosystem"])

    return known


def extract_signature_info(body_text, sender_name, location_hints=None):
    """Try to extract title and organization from email signature."""
    if not body_text:
        return {}

    lines = body_text.strip().split("\n")
    result = {}

    sig_start = None
    for i in range(len(lines) - 1, max(len(lines) - 40, -1), -1):
        line = lines[i].strip()
        if SIG_DELIMITERS.match(line):
            sig_start = i
            break

    if sig_start is None:
        for i in range(len(lines) - 1, max(len(lines) - 15, -1), -1):
            line = lines[i].strip()
            if sender_name and _name_match(line, sender_name):
                sig_start = i
                break

    if sig_start is None:
        return {}

    sig_lines = []
    for i in range(sig_start, min(sig_start + 10, len(lines))):
        line = lines[i].strip()
        if line and not SIG_DELIMITERS.match(line):
            sig_lines.append(line)

    if not sig_lines:
        return {}

    result["signature_block"] = "\n".join(sig_lines)

    for line in sig_lines:
        if TITLE_PATTERNS.search(line):
            title_candidate = line.strip().rstrip(",").strip()
            if sender_name and _name_match(title_candidate, sender_name):
                continue
            if len(title_candidate) > 100:
                continue
            result["extracted_title"] = title_candidate
            break

    if location_hints:
        escaped = [re.escape(h) for h in location_hints]
        location_pattern = re.compile("|".join(escaped), re.IGNORECASE)
    else:
        location_pattern = re.compile(
            r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}(?:\s+\d{5})?",
        )

    for line in sig_lines:
        if location_pattern.search(line):
            result["extracted_location"] = line.strip()
            break

    return result


def _name_match(text, name):
    """Check if text contains the person's name (fuzzy)."""
    if not name or not text:
        return False
    text_lower = text.lower()
    name_lower = name.lower()

    if name_lower in text_lower:
        return True

    parts = name_lower.split()
    if len(parts) >= 2:
        if parts[0] in text_lower and parts[-1] in text_lower:
            return True

    return False


def classify_domain(email_addr, domains, domain_labels):
    """Classify an email address by its domain."""
    if not email_addr:
        return None, None

    addr_domain = email_addr.lower().split("@")[-1] if "@" in email_addr else None
    if not addr_domain:
        return None, None

    for d in domains:
        if addr_domain == d or addr_domain.endswith("." + d):
            return d, domain_labels.get(d, d)

    return None, None


def process_emails(email_dir, config):
    """Main processing function."""
    domains = config["domains"]
    domain_labels = config["domain_labels"]
    org_chart_path = config["org_chart"]
    checkpoint_path = config["checkpoint"]
    ignore_list_path = config.get("ignore_list", "")
    reprocess = config.get("reprocess", False)
    output_path = config.get("output")
    contractor_patterns = [re.compile(p) for p in config.get("contractor_patterns", [])]
    location_hints = config.get("location_hints", [])

    if not domains:
        print("ERROR: No domains configured. Check _company/company_config.json.", file=sys.stderr)
        return None

    index_path = os.path.join(email_dir, "index.json")
    if not os.path.exists(index_path):
        print(f"ERROR: index.json not found in {email_dir}", file=sys.stderr)
        return None

    index = load_json(index_path)
    emails = index.get("emails", [])

    if not org_chart_path or not os.path.exists(org_chart_path):
        print(f"ERROR: Org chart not found at {org_chart_path}", file=sys.stderr)
        return None

    org_chart = load_json(org_chart_path)
    known_people = build_known_people(org_chart)

    ignored_emails = set()
    if ignore_list_path and os.path.exists(ignore_list_path):
        try:
            ignore_data = load_json(ignore_list_path)
            ignored_emails = {e.lower() for e in ignore_data.get("ignored", [])}
        except Exception:
            pass

    processed_ids = set()
    if not reprocess and checkpoint_path and os.path.exists(checkpoint_path):
        try:
            cp = load_json(checkpoint_path)
            processed_ids = set(cp.get("processed_ids", []))
        except Exception:
            processed_ids = set()

    # --- Scan emails ---
    new_people = defaultdict(lambda: {
        "email": "",
        "name": "",
        "domain": "",
        "org": "",
        "seen_in": [],
        "roles": set(),
        "context_subjects": [],
        "first_seen": None,
        "correspondents": set(),
    })

    known_signals = defaultdict(lambda: {
        "email": "",
        "name": "",
        "new_subjects": [],
        "email_count": 0,
        "correspondents": set(),
    })

    emails_processed = 0
    emails_skipped = 0

    for email in emails:
        eid = email.get("id", "")

        if eid in processed_ids:
            emails_skipped += 1
            continue

        subject = email.get("subject", "")
        date = email.get("date", "")
        from_email = (email.get("from_email") or "").strip().lower()
        from_name = email.get("from_name", "")

        people_in_email = []

        if from_email:
            people_in_email.append({
                "email": from_email,
                "name": from_name,
                "role": "sender",
            })

        for recip in email.get("to_recipients", []):
            r_email = (recip.get("email") or "").strip().lower()
            if r_email:
                people_in_email.append({
                    "email": r_email,
                    "name": recip.get("name", ""),
                    "role": "to",
                })

        for recip in email.get("cc_recipients", []):
            r_email = (recip.get("email") or "").strip().lower()
            if r_email:
                people_in_email.append({
                    "email": r_email,
                    "name": recip.get("name", ""),
                    "role": "cc",
                })

        relevant_people = []
        for p in people_in_email:
            domain, org = classify_domain(p["email"], domains, domain_labels)
            if domain:
                p["domain"] = domain
                p["org"] = org
                relevant_people.append(p)

        all_email_addrs = {p["email"] for p in relevant_people}

        for p in relevant_people:
            addr = p["email"]

            if addr in ignored_emails:
                continue

            if addr in known_people:
                sig = known_signals[addr]
                sig["email"] = addr
                sig["name"] = known_people[addr]["name"]
                sig["email_count"] += 1
                if subject and subject not in sig["new_subjects"]:
                    sig["new_subjects"].append(subject)
                sig["correspondents"].update(all_email_addrs - {addr})
            else:
                entry = new_people[addr]
                entry["email"] = addr
                entry["name"] = entry["name"] or p["name"]
                entry["domain"] = p["domain"]
                entry["org"] = p["org"]
                if eid not in entry["seen_in"]:
                    entry["seen_in"].append(eid)
                entry["roles"].add(p["role"])
                if subject and subject not in entry["context_subjects"]:
                    entry["context_subjects"].append(subject)
                if not entry["first_seen"] or (date and date < entry["first_seen"]):
                    entry["first_seen"] = date
                entry["correspondents"].update(all_email_addrs - {addr})

        processed_ids.add(eid)
        emails_processed += 1

    # --- Extract signatures for new people who were senders ---
    sender_emails = {}
    for email in emails:
        from_email = (email.get("from_email") or "").strip().lower()
        if from_email in new_people:
            body_file = email.get("body_file")
            if body_file:
                body_path = os.path.join(email_dir, body_file)
                if os.path.exists(body_path):
                    try:
                        with open(body_path, "r", encoding="utf-8", errors="replace") as f:
                            body_text = f.read()
                        sig_info = extract_signature_info(
                            body_text, email.get("from_name", ""),
                            location_hints=location_hints,
                        )
                        if sig_info and from_email not in sender_emails:
                            sender_emails[from_email] = sig_info
                    except Exception:
                        pass

    for addr, sig_info in sender_emails.items():
        if addr in new_people:
            new_people[addr].update(sig_info)

    # --- Check for contractor signals ---
    for addr, entry in new_people.items():
        local_part = addr.split("@")[0] if "@" in addr else ""
        for pattern in contractor_patterns:
            if pattern.match(local_part):
                entry["contractor_signal"] = True
                break

    # --- Build report ---
    new_people_list = []
    for addr, entry in sorted(new_people.items(), key=lambda x: x[1]["org"]):
        new_people_list.append({
            "email": entry["email"],
            "name": entry["name"],
            "domain": entry["domain"],
            "org": entry["org"],
            "seen_count": len(entry["seen_in"]),
            "roles": sorted(entry["roles"]),
            "context_subjects": entry["context_subjects"][:10],
            "first_seen": entry["first_seen"],
            "correspondents": sorted(entry["correspondents"])[:20],
            "extracted_title": entry.get("extracted_title"),
            "extracted_location": entry.get("extracted_location"),
            "signature_block": entry.get("signature_block"),
            "contractor_signal": entry.get("contractor_signal", False),
        })

    known_signals_list = []
    for addr, sig in sorted(known_signals.items(), key=lambda x: -x[1]["email_count"]):
        known_signals_list.append({
            "email": sig["email"],
            "name": sig["name"],
            "email_count": sig["email_count"],
            "new_subjects": sig["new_subjects"][:10],
            "correspondents": sorted(sig["correspondents"])[:20],
        })

    report = {
        "generated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "email_export": email_dir,
        "stats": {
            "emails_in_export": len(emails),
            "emails_processed": emails_processed,
            "emails_skipped_checkpoint": emails_skipped,
            "new_people_found": len(new_people_list),
            "known_people_with_signals": len(known_signals_list),
            "ignored_emails": len(ignored_emails),
            "domains_scanned": domains,
        },
        "new_people": new_people_list,
        "known_people_signals": known_signals_list,
    }

    if output_path is None:
        output_path = os.path.join(email_dir, "people_report.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Update checkpoint
    if checkpoint_path:
        checkpoint = {
            "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "processed_ids": sorted(processed_ids),
            "total_processed": len(processed_ids),
        }
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)

    return report, output_path


def print_summary(report):
    """Print a human-readable summary of the report."""
    stats = report["stats"]
    print(f"\n=== People Processor Report ===")
    print(f"  Emails processed: {stats['emails_processed']}")
    print(f"  Skipped (checkpoint): {stats['emails_skipped_checkpoint']}")
    print(f"  New people found: {stats['new_people_found']}")
    print(f"  Known people w/signals: {stats['known_people_with_signals']}")
    print(f"  Ignored addresses: {stats['ignored_emails']}")
    print(f"  Domains: {', '.join(stats['domains_scanned'])}")

    if report["new_people"]:
        print(f"\n--- New People ---")
        for p in report["new_people"]:
            contractor = " [CONTRACTOR?]" if p["contractor_signal"] else ""
            title = f" — {p['extracted_title']}" if p["extracted_title"] else ""
            print(f"  {p['name']} <{p['email']}> ({p['org']}){title}{contractor}")
            print(f"    Seen in {p['seen_count']} emails, roles: {', '.join(p['roles'])}")
            if p["context_subjects"]:
                print(f"    Subjects: {p['context_subjects'][0]}")

    if report["known_people_signals"]:
        print(f"\n--- Known People Activity ---")
        for p in report["known_people_signals"][:10]:
            print(f"  {p['name']}: {p['email_count']} emails")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan email exports for new/updated people signals."
    )
    parser.add_argument("email_dir", help="Path to email output directory (contains index.json)")
    parser.add_argument("-c", "--config", default=None, help="Path to people_config.json (auto-discovered)")
    parser.add_argument("--company-config", default=None, help="Path to company_config.json (auto-discovered)")
    parser.add_argument("--org-chart", default=None, help="Override org chart path")
    parser.add_argument("--checkpoint", default=None, help="Override checkpoint path")
    parser.add_argument("--reprocess", action="store_true", help="Ignore checkpoint, reprocess all")
    parser.add_argument("--domains", default=None, help="Override domains (comma-separated)")
    parser.add_argument("--output", default=None, help="Path to write report JSON")
    parser.add_argument("--ignore-list", default=None, help="Override ignore list path")

    args = parser.parse_args()

    config, config_path = load_config(
        config_path=args.config,
        company_config_path=args.company_config,
    )

    if args.org_chart:
        config["org_chart"] = args.org_chart
    if args.checkpoint:
        config["checkpoint"] = args.checkpoint
    if args.ignore_list:
        config["ignore_list"] = args.ignore_list
    if args.domains:
        config["domains"] = [d.strip() for d in args.domains.split(",")]
    config["reprocess"] = args.reprocess
    config["output"] = args.output

    result = process_emails(
        email_dir=args.email_dir,
        config=config,
    )

    if result is None:
        sys.exit(1)

    report, output_path = result
    print_summary(report)
    print(f"\n  Report: {output_path}")
    print(f"  Checkpoint: {config['checkpoint']}")


if __name__ == "__main__":
    main()
