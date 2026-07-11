#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPU6050 Terminal Monitör
========================
LoRa üzerinden gelen ham ve filtrelenmiş ivmeölçer verilerini
terminalde renkli tablo formatında gösterir.

Veri Formatı: HX:0.123 FX:0.456 HY:0.789 FY:0.012 HZ:0.345 FZ:0.678
  - HX/HY/HZ: Ham (filtresiz) ivme değerleri (g)
  - FX/FY/FZ: Filtrelenmiş ivme değerleri (g)

Kullanım:
  python mpu6050_monitor.py          (otomatik COM port bulma)
  python mpu6050_monitor.py COM5     (belirli port)
"""

import serial
import serial.tools.list_ports
import sys
import re
import time
import os
from datetime import datetime

# ─── Renk Kodları (Windows Terminal / ANSI) ──────────────────────────────
class Colors:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    
    # Başlıklar
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    YELLOW  = "\033[93m"
    GREEN   = "\033[92m"
    RED     = "\033[91m"
    BLUE    = "\033[94m"
    WHITE   = "\033[97m"
    
    # Arka plan
    BG_DARK = "\033[48;5;236m"
    BG_HEAD = "\033[48;5;17m"


# ─── Konfigürasyon ──────────────────────────────────────────────────────
BAUD_RATE = 9600
TIMEOUT   = 2  # saniye

def find_com_port():
    """Bağlı COM portlarını listele ve seçim yap."""
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print(f"{Colors.RED}✖ Hiçbir COM portu bulunamadı!{Colors.RESET}")
        print(f"{Colors.DIM}  USB-TTL adaptörünüzün bağlı olduğundan emin olun.{Colors.RESET}")
        sys.exit(1)
    
    if len(ports) == 1:
        port = ports[0]
        print(f"{Colors.GREEN}✔ Otomatik port seçildi: {Colors.BOLD}{port.device}{Colors.RESET}"
              f" {Colors.DIM}({port.description}){Colors.RESET}")
        return port.device
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}═══ Bulunan COM Portları ═══{Colors.RESET}\n")
    for i, port in enumerate(ports):
        print(f"  {Colors.YELLOW}[{i+1}]{Colors.RESET} {Colors.WHITE}{port.device}{Colors.RESET}"
              f"  →  {Colors.DIM}{port.description}{Colors.RESET}")
    
    print()
    while True:
        try:
            choice = input(f"{Colors.CYAN}Port numarası seçin (1-{len(ports)}): {Colors.RESET}")
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                return ports[idx].device
        except (ValueError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}İptal edildi.{Colors.RESET}")
            sys.exit(0)


def parse_line(line):
    """
    Gelen satırı parse et.
    Format: HX:0.123 FX:0.456 HY:0.789 FY:0.012 HZ:0.345 FZ:0.678
    """
    pattern = (
        r"HX:([-\d.]+)\s+FX:([-\d.]+)\s+"
        r"HY:([-\d.]+)\s+FY:([-\d.]+)\s+"
        r"HZ:([-\d.]+)\s+FZ:([-\d.]+)"
    )
    match = re.search(pattern, line)
    if match:
        return {
            'HX': float(match.group(1)),
            'FX': float(match.group(2)),
            'HY': float(match.group(3)),
            'FY': float(match.group(4)),
            'HZ': float(match.group(5)),
            'FZ': float(match.group(6)),
        }
    return None


def print_banner():
    """Başlangıç banner'ı yazdır."""
    os.system("")  # Windows'ta ANSI renk desteğini aktifleştir
    
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
  ╔══════════════════════════════════════════════════════════════╗
  ║          MPU6050 Dual Sensor - Terminal Monitör             ║
  ║       Ham (Sensor1) vs Filtrelenmiş (Sensor2) Veriler      ║
  ╚══════════════════════════════════════════════════════════════╝
{Colors.RESET}"""
    print(banner)


def format_value(val, width=9):
    """Değeri formatlı string'e çevir, büyüklüğe göre renk ver."""
    s = f"{val:+{width}.4f}"
    abs_val = abs(val)
    if abs_val > 1.5:
        return f"{Colors.RED}{s}{Colors.RESET}"
    elif abs_val > 0.8:
        return f"{Colors.YELLOW}{s}{Colors.RESET}"
    else:
        return f"{Colors.GREEN}{s}{Colors.RESET}"


def print_header():
    """Tablo başlığını yazdır."""
    print(f"\n{Colors.BG_HEAD}{Colors.WHITE}{Colors.BOLD}"
          f"  {'Zaman':>12}  │  {'Eksen':^5}  │  {'Ham (g)':^11}  │  {'Filtreli (g)':^11}  │  {'Δ (Fark)':^11}  "
          f"{Colors.RESET}")
    print(f"{Colors.DIM}  {'─'*12}──┼──{'─'*5}──┼──{'─'*11}──┼──{'─'*11}──┼──{'─'*11}──{Colors.RESET}")


def print_data(data, count):
    """Veriyi formatlı tablo olarak yazdır."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    axes = [
        ('X', data['HX'], data['FX']),
        ('Y', data['HY'], data['FY']),
        ('Z', data['HZ'], data['FZ']),
    ]
    
    for i, (axis, raw, filt) in enumerate(axes):
        diff = filt - raw
        
        time_str = f"{Colors.DIM}{timestamp}{Colors.RESET}" if i == 0 else " " * 12
        axis_color = [Colors.RED, Colors.GREEN, Colors.BLUE][i]
        
        print(f"  {time_str}  │  {axis_color}{Colors.BOLD}  {axis}  {Colors.RESET}  │  "
              f"{format_value(raw)}  │  {format_value(filt)}  │  {format_value(diff)}  ")
    
    # Her 3 satırda bir ayırıcı çizgi
    if count % 5 == 0:
        print(f"{Colors.DIM}  {'─'*12}──┼──{'─'*5}──┼──{'─'*11}──┼──{'─'*11}──┼──{'─'*11}──{Colors.RESET}")


def main():
    print_banner()
    
    # COM port belirleme
    if len(sys.argv) > 1:
        port = sys.argv[1]
        print(f"{Colors.GREEN}✔ Belirtilen port: {Colors.BOLD}{port}{Colors.RESET}")
    else:
        port = find_com_port()
    
    # Seri port bağlantısı
    print(f"\n{Colors.CYAN}▸ Bağlanılıyor: {port} @ {BAUD_RATE} baud...{Colors.RESET}")
    
    try:
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = BAUD_RATE
        ser.timeout = TIMEOUT
        ser.bytesize = serial.EIGHTBITS
        ser.parity = serial.PARITY_NONE
        ser.stopbits = serial.STOPBITS_ONE
        ser.xonxoff = False
        ser.rtscts = False
        ser.dsrdtr = False
        ser.open()
        ser.dtr = False
        ser.rts = False
        time.sleep(0.5)  # Bağlantı stabilizasyonu
        ser.reset_input_buffer()
        print(f"{Colors.GREEN}{Colors.BOLD}✔ Bağlantı başarılı!{Colors.RESET}")
        print(f"{Colors.DIM}  Çıkmak için Ctrl+C basın{Colors.RESET}")
    except serial.SerialException as e:
        print(f"{Colors.RED}✖ Seri port hatası: {e}{Colors.RESET}")
        sys.exit(1)
    
    print_header()
    
    count = 0
    error_count = 0
    
    try:
        while True:
            try:
                raw_line = ser.readline()
                if not raw_line:
                    continue
                
                line = raw_line.decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                
                data = parse_line(line)
                if data:
                    count += 1
                    print_data(data, count)
                    error_count = 0
                else:
                    error_count += 1
                    if error_count <= 3:
                        print(f"{Colors.DIM}  ⚠ Parse edilemeyen satır: {line[:60]}{Colors.RESET}")
                    
            except UnicodeDecodeError:
                continue
                
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}{Colors.BOLD}■ Durduruldu.{Colors.RESET}")
        print(f"{Colors.DIM}  Toplam {count} veri paketi alındı.{Colors.RESET}\n")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
