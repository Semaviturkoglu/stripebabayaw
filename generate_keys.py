# --- DOSYA: generate_keys.py ---
import secrets

def generate_keys(count=100, is_admin=False):
    filename = "admin_keys.txt" if is_admin else "keys.txt"
    keys = [secrets.token_urlsafe(24) for _ in range(count)]
    with open(filename, "a") as f: # "a" (append) modunda açıyoruz ki üzerine yazmasın
        for key in keys:
            f.write(f"{key}\n")
    print(f"{count} adet yeni {'admin' if is_admin else 'kullanıcı'} anahtarı '{filename}' dosyasına eklendi.")

if __name__ == '__main__':
    # Kullanımı: Shell'e "python generate_keys.py" veya "python generate_keys.py admin" yaz.
    import sys
    is_admin_key = len(sys.argv) > 1 and sys.argv[1] == 'admin'
    generate_keys(is_admin=is_admin_key)
