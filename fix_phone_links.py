#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_phone_links.py — Update tel:+31614392215 links for mobile/desktop routing.

- Mobile:  keep tel: link + fire GA4 phone_call event
- Desktop: redirect to WhatsApp instead
"""

import os
import re
import sys
import io

# Force UTF-8 output so emoji in HTML don't cause encoding errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

WHATSAPP_URL = "https://wa.me/31614392215?text=Hallo%2C%20ik%20heb%20een%20vraag%20over%20ontstopping"

# Plain string for substring checks (no regex escapes)
TEL_SUBSTR = "tel:+31614392215"

total_pattern_a = 0
total_pattern_b = 0
files_changed = []


def build_pattern_a_replacement(gtag_params: str) -> str:
    """
    Build new onclick for Pattern A.
    gtag_params: the params object, e.g. {'event_category':'bellen','event_label':'hero'}
    Mobile  -> phone_call event fires, tel: link opens normally
    Desktop -> WhatsApp opens, whatsapp_click event fires
    """
    onclick = (
        "if(/Mobi|Android/i.test(navigator.userAgent)){"
        f"gtag('event','phone_call',{gtag_params});}}else{{"
        "event.preventDefault();"
        f"window.open('{WHATSAPP_URL}','_blank');"
        f"gtag('event','whatsapp_click',{gtag_params});}}"
    )
    return onclick


def process_pattern_a(content: str):
    """
    Pattern A: <a> tags with href=tel:+31614392215 AND onclick="gtag('event','phone_call',{...});"
    Wraps the existing gtag call in a mobile check, adds WhatsApp fallback for desktop.
    Handles tags that may span multiple lines.
    Returns (new_content, count_replaced)
    """
    count = 0

    # Match full <a ...> opening tag (handles multiline via DOTALL)
    # [^>]* would fail if > appears in attribute values, but our onclick uses ; not >
    # Using a safer pattern that matches balanced quotes
    tag_re = re.compile(
        r'(<a\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*href="tel:\+31614392215"(?:[^>"\']|"[^"]*"|\'[^\']*\')*>)',
        re.DOTALL
    )

    # Regex to find onclick with phone_call gtag (both quote styles for params)
    onclick_re = re.compile(
        r"""onclick="gtag\('event','phone_call',(\{[^}]+\})\);" """,
        re.DOTALL
    )
    # Version without trailing space (end of attributes before class= etc.)
    onclick_re2 = re.compile(
        r"""onclick="gtag\('event','phone_call',(\{[^}]+\})\);"(?=[^"]*")""",
        re.DOTALL
    )
    # Most general: just find onclick="gtag('event','phone_call',{...});"
    onclick_general = re.compile(
        r"""onclick="gtag\('event','phone_call',(\{[^}]+\})(?:\s*)\);\s*" """,
        re.DOTALL
    )

    def replace_tag(m):
        nonlocal count
        tag = m.group(1)

        # Skip if already has mobile check
        if 'Mobi|Android' in tag:
            return tag

        # Find onclick with phone_call
        om = re.search(r"""onclick="gtag\('event','phone_call',(\{[^}]+\})\);\s*" """, tag, re.DOTALL)
        if not om:
            # Try without trailing space (e.g. onclick="..." class=)
            om = re.search(r"""onclick="gtag\('event','phone_call',(\{[^}]+\})\);\s*"(?=\s)""", tag, re.DOTALL)
        if not om:
            # Try catching it at end of onclick value boundary
            om = re.search(r'onclick="gtag\(\'event\',\'phone_call\',(\{[^}]+\})\);"', tag, re.DOTALL)
        if not om:
            return tag  # No matching gtag onclick

        gtag_params = om.group(1)
        new_onclick = build_pattern_a_replacement(gtag_params)
        # Replace the entire onclick="..." portion
        new_tag = tag[:om.start()] + f'onclick="{new_onclick}"' + tag[om.end():]
        count += 1
        return new_tag

    new_content = tag_re.sub(replace_tag, content)
    return new_content, count


def process_pattern_b(content: str):
    """
    Pattern B: <a> tags with href=tel:+31614392215 WITHOUT any onclick.
    Adds onclick for desktop WhatsApp redirect (mobile: tel: link works normally).
    Returns (new_content, count_replaced)
    """
    count = 0
    wa_onclick = (
        f"if(!/Mobi|Android/i.test(navigator.userAgent)){{"
        f"event.preventDefault();"
        f"window.open('{WHATSAPP_URL}','_blank');}}"
    )

    tag_re = re.compile(
        r'(<a\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*href="tel:\+31614392215"(?:[^>"\']|"[^"]*"|\'[^\']*\')*>)',
        re.DOTALL
    )

    def replace_tag(m):
        nonlocal count
        tag = m.group(1)

        # Skip if already has mobile check (Pattern A already processed it, or previously done)
        if 'Mobi|Android' in tag:
            return tag

        # Skip if it has any onclick (shouldn't happen for Pattern B, but be safe)
        if 'onclick=' in tag:
            return tag

        # Insert onclick just before the closing >
        # tag ends with >
        new_tag = tag[:-1] + f' onclick="{wa_onclick}">'
        count += 1
        return new_tag

    new_content = tag_re.sub(replace_tag, content)
    return new_content, count


def process_file(filepath: str):
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    # Quick check: skip files that don't contain our tel number
    if TEL_SUBSTR not in original:
        return 0, 0

    # Pattern A first (links with existing gtag phone_call onclick)
    after_a, count_a = process_pattern_a(original)

    # Pattern B next (remaining links without phone_call onclick)
    after_b, count_b = process_pattern_b(after_a)

    if count_a + count_b > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(after_b)

    return count_a, count_b


def find_html_files(root: str):
    html_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden directories (e.g. .git)
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for fname in filenames:
            if fname.endswith('.html'):
                html_files.append(os.path.join(dirpath, fname))
    return sorted(html_files)


def main():
    global total_pattern_a, total_pattern_b

    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_files = find_html_files(script_dir)

    print(f"Found {len(html_files)} HTML files\n")

    for fpath in html_files:
        count_a, count_b = process_file(fpath)
        rel = os.path.relpath(fpath, script_dir)
        if count_a + count_b > 0:
            print(f"  CHANGED  {rel}: Pattern A={count_a}, Pattern B={count_b}")
            files_changed.append(rel)
            total_pattern_a += count_a
            total_pattern_b += count_b
        else:
            # Warn if file has tel: but nothing was replaced
            with open(fpath, 'r', encoding='utf-8') as f:
                c = f.read()
            if TEL_SUBSTR in c:
                print(f"  WARNING: {rel} has tel: links but 0 replacements made!")
            else:
                print(f"  skipped  {rel}")

    print(f"\n=== SUMMARY ===")
    print(f"Files changed:      {len(files_changed)}")
    print(f"Pattern A replaced: {total_pattern_a}")
    print(f"Pattern B replaced: {total_pattern_b}")
    print(f"Total replacements: {total_pattern_a + total_pattern_b}")


if __name__ == '__main__':
    main()
