import pathlib
p = pathlib.Path("book.py")
d = p.read_bytes()

# Add debug logging after each step
old = b"        log.info(\"=== CAS Login ===\")"
new = b"        log.info(\"=== CAS Login ===\")\r\n        # DEBUG\r\n        print(\"Step 1: visiting BASE...\")"
d = d.replace(old, new)

old = b"        r = self.s.get(BASE, allow_redirects=True, timeout=15)"
new = b"        r = self.s.get(BASE, allow_redirects=True, timeout=15)\r\n        print(f\"Step 2: redirected to {r.url[:120]}\")"
d = d.replace(old, new)

old = b"        if not salt: raise RuntimeError(\"Cannot get encryption salt\")"
new = b"        print(f\"Step 3: salt={salt[:20]}, exe={exe}\")\r\n        if not salt: raise RuntimeError(\"Cannot get encryption salt\")"
d = d.replace(old, new)

old = b"        enc_pwd = encrypt_password(password, salt)"
new = b"        enc_pwd = encrypt_password(password, salt)\r\n        print(f\"Step 4: enc_pwd={enc_pwd[:50]}...\")"
d = d.replace(old, new)

old = b"        r = self.s.post(r.url, data=login_data, allow_redirects=True, timeout=15)"
new = b"        r = self.s.post(r.url, data=login_data, allow_redirects=True, timeout=15)\r\n        print(f\"Step 5: POST result URL={r.url[:120]}, history={len(r.history)}\")\r\n        for i, h in enumerate(r.history):\r\n            print(f\"  redirect [{i}]: {h.status_code} -> {h.url[:120]}\")"
d = d.replace(old, new)

p.write_bytes(d)
print("Debug added")
