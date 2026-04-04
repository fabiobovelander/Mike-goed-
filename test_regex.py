#!/usr/bin/env python3
import re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

script_dir = os.path.dirname(os.path.abspath(__file__))
print('script_dir:', script_dir)

TEL_PATTERN = 'tel:+31614392215'

files = []
for dirpath, dirnames, filenames in os.walk(script_dir):
    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
    for fname in filenames:
        if fname.endswith('.html'):
            files.append(os.path.join(dirpath, fname))
print('HTML files:', len(files))

# Test regex on index.html
idx_path = os.path.join(script_dir, 'index.html')
content = open(idx_path, encoding='utf-8').read()
print('tel: in index.html:', TEL_PATTERN in content)

tag_re = re.compile(r'(<a\b[^>]*href=["\']tel:\+31614392215["\'][^>]*>)', re.DOTALL)
matches = list(tag_re.finditer(content))
print('Tag regex matches in index.html:', len(matches))
