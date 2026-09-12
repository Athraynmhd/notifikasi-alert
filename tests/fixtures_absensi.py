"""Minimal HTML fixtures for state_of() — mirror heuristik SIMKULIAH."""

HTML_NOT_OPEN = """
<html><body>
<div class="user-profile"><h4>Athar Rayyan</h4></div>
<p>Status: Belum masuk waktu absen</p>
</body></html>
"""

HTML_OPEN = """
<html><body>
<div class="user-profile"><h4>Athar Rayyan</h4></div>
<a class="btn btn-absen" href="/index.php/absensi/do_absen">Absen Sekarang</a>
</body></html>
"""

HTML_OPEN_FORM = """
<html><body>
<form action="/index.php/absensi/do_absen" method="post">
  <input type="hidden" name="token" value="abc" />
  <button type="submit">Absen</button>
</form>
</body></html>
"""

HTML_UNKNOWN = """
<html><body>
<div>Dashboard mahasiswa</div>
<p>Tidak ada indikator absensi yang dikenali.</p>
</body></html>
"""

HTML_NOT_OPEN_WITH_STALE_BTN = """
<html><body>
<p>Belum masuk waktu absen</p>
<!-- tombol jangan dianggap OPEN -->
<a class="btn-absen" href="#">x</a>
</body></html>
"""
