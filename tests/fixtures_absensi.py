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

HTML_BATAS_ACTIVE = """
<html><body>
<div class="card">
  <div>Absensi Kelas A | MMAI1007 - MANAJEMEN DAN PEMODELAN DATA | Pertemuan ke-5</div>
  <div class="alert">Mahasiswa hanya dapat melakukan presensi dalam rentang waktu 15 menit setelah dosen melakukan presensi.</div>
  <p>Anda belum absen</p>
  <a class="btn btn-absen" href="/index.php/absensi/do_absen">Konfirmasi Kehadiran</a>
  <table>
    <thead><tr>
      <th>Kelas</th><th>Gedung</th><th>Ruang</th><th>Jam</th><th>Batas Absen</th>
    </tr></thead>
    <tbody><tr>
      <td>A</td><td>Gedung MIPA</td><td>B.01.01</td><td>08.00 - 10.30</td><td>09:05</td>
    </tr></tbody>
  </table>
</div>
</body></html>
"""

HTML_BATAS_EXPIRED_SUDAH = """
<html><body>
<div class="card">
  <div>Absensi Kelas A | MMAI1007 - MANAJEMEN DAN PEMODELAN DATA | Pertemuan ke-5</div>
  <p>Anda sudah absen</p>
  <table>
    <thead><tr>
      <th>Kelas</th><th>Gedung</th><th>Ruang</th><th>Jam</th><th>Batas Absen</th>
    </tr></thead>
    <tbody><tr>
      <td>A</td><td>Gedung MIPA</td><td>B.01.01</td><td>08.00 - 10.30</td><td>09:05</td>
    </tr></tbody>
  </table>
</div>
</body></html>
"""

HTML_BATAS_DOSEN_BELUM = """
<html><body>
<div class="card">
  <div>Absensi Kelas A | MMAI1005 - PRAKTIKUM | Pertemuan ke-1</div>
  <p>Anda belum absen</p>
  <button>Konfirmasi Kehadiran</button>
  <table>
    <thead><tr>
      <th>Kelas</th><th>Gedung</th><th>Ruang</th><th>Jam</th><th>Batas Absen</th>
    </tr></thead>
    <tbody><tr>
      <td>A</td><td>Gedung MIPA</td><td>Lab</td><td>09.50 - 11.30</td><td>Dosen belum absen</td>
    </tr></tbody>
  </table>
</div>
</body></html>
"""
