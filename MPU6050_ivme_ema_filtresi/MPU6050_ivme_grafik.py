"""
LoRa Gerçek Zamanlı İvme Grafiği
==================================
STM32'den gelen "HX FY HZ FX FY FZ" formatındaki
ham ve filtreli ivme verilerini gösterir.

Kurulum:  pip install pyserial matplotlib
Çalıştır: python lora_plotter.py
"""

import serial
import threading
import time
import collections
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
PORT        = "COM3"
BAUD_RATE   = 9600
TIMEOUT_S   = 0.5      # 9600'de paket arasi ~150ms
MAX_BUF     = 256
WINDOW_SIZE = 100      # 100 x 150ms = ~15 saniyelik pencere
LOG_TO_FILE = True
LOG_FILE    = "lora_accel_log.csv"
# ──────────────────────────────────────────────

# ── Renk paleti ───────────────────────────────
CLR_BG      = "#0f1117"
CLR_PANEL   = "#1a1d27"
CLR_BORDER  = "#2a2d3a"
CLR_GRID    = "#1e2130"
CLR_TEXT    = "#e2e8f0"
CLR_SUBTEXT = "#64748b"
CLR_GOOD    = "#4ade80"
CLR_BAD     = "#f87171"

# Ham çizgi renkleri — X, Y, Z eksenleri
HAM_COLORS = {
    "X": "#f97316",   # turuncu
    "Y": "#a78bfa",   # mor
    "Z": "#38bdf8",   # mavi
}
# Filtreli çizgi renkleri — her eksen için farklı, doygun ton
FILT_COLORS = {
    "X": "#facc15",   # sarı
    "Y": "#34d399",   # yeşil
    "Z": "#f472b6",   # pembe
}
# ──────────────────────────────────────────────

# ── Paylaşılan veri deposu ────────────────────
data_lock = threading.Lock()
KEYS = ["HX", "HY", "HZ", "FX", "FY", "FZ"]
queues = {k: collections.deque(maxlen=WINDOW_SIZE) for k in KEYS}
times  = collections.deque(maxlen=WINDOW_SIZE)
latest = {k: 0.0 for k in KEYS}
latest.update({"pkts": 0, "errs": 0, "connected": False})
# ──────────────────────────────────────────────


# ═══════════════════════════════════════════════
#  SERIAL OKUMA THREAD'İ
# ═══════════════════════════════════════════════
def parse_packet(line: str):
    """
    "HX:0.012 HY:-0.005 HZ:1.001 FX:0.011 FY:-0.004 FZ:0.998"
    → {"HX": 0.012, "HY": -0.005, ...} veya None
    """
    try:
        parts = {}
        for token in line.split():
            if ":" in token:
                k, v = token.split(":", 1)
                parts[k] = float(v)
        if all(k in parts for k in KEYS):
            return parts
    except (ValueError, AttributeError):
        pass
    return None


def serial_reader():
    log_f = None
    if LOG_TO_FILE:
        log_f = open(LOG_FILE, "a", encoding="utf-8")
        if log_f.tell() == 0:
            log_f.write("timestamp," + ",".join(KEYS) + "\n")

    buf       = bytearray()
    last_byte = time.monotonic()

    while True:
        try:
            ser = serial.Serial(PORT, BAUD_RATE, timeout=0)
            with data_lock:
                latest["connected"] = True

            while True:
                waiting = ser.in_waiting
                if waiting:
                    buf.extend(ser.read(waiting))
                    last_byte = time.monotonic()

                # Zaman aşımı → buffer temizle
                if buf and (time.monotonic() - last_byte) > TIMEOUT_S:
                    buf = bytearray()
                    with data_lock:
                        latest["errs"] += 1

                # Taşma koruması
                if len(buf) > MAX_BUF:
                    buf = bytearray()
                    with data_lock:
                        latest["errs"] += 1

                # Paket tespiti
                while b"\r\n" in buf:
                    idx  = buf.index(b"\r\n")
                    line = buf[:idx].decode("ascii", errors="replace").strip()
                    buf  = buf[idx + 2:]

                    data = parse_packet(line)
                    if data:
                        with data_lock:
                            times.append(time.monotonic())
                            for k in KEYS:
                                queues[k].append(data[k])
                            latest.update(data)
                            latest["pkts"] += 1

                        if log_f:
                            row = ",".join(str(data[k]) for k in KEYS)
                            log_f.write(f"{datetime.now().isoformat()},{row}\n")
                            log_f.flush()
                    elif line:
                        with data_lock:
                            latest["errs"] += 1

                time.sleep(0.005)

        except serial.SerialException:
            with data_lock:
                latest["connected"] = False
            buf = bytearray()
            time.sleep(2)


# ═══════════════════════════════════════════════
#  GRAFİK KURULUMU
# ═══════════════════════════════════════════════
def build_figure():
    fig = plt.figure(figsize=(13, 9), facecolor=CLR_BG)
    fig.canvas.manager.set_window_title("LoRa İvme Gösterici — STM32 MPU6050")

    gs = gridspec.GridSpec(
        4, 3,
        figure=fig,
        height_ratios=[1, 1, 1, 0.28],
        hspace=0.42, wspace=0.3,
        left=0.07, right=0.97,
        top=0.91, bottom=0.07,
    )

    axes = {
        "X": fig.add_subplot(gs[0, :]),
        "Y": fig.add_subplot(gs[1, :]),
        "Z": fig.add_subplot(gs[2, :]),
    }
    ax_stat = fig.add_subplot(gs[3, :])

    for ax in list(axes.values()) + [ax_stat]:
        ax.set_facecolor(CLR_PANEL)
        for spine in ax.spines.values():
            spine.set_color(CLR_BORDER)

    return fig, axes, ax_stat


def style_axis(ax, axis_letter):
    color = HAM_COLORS[axis_letter]
    ax.set_title(f"İVME — {axis_letter} EKSENİ",
                 color=color, fontsize=10, fontweight="bold",
                 loc="left", pad=6)
    ax.set_ylabel("g", color=CLR_SUBTEXT, fontsize=9)
    ax.tick_params(colors=CLR_SUBTEXT, labelsize=8)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.3f g"))
    ax.xaxis.set_visible(False)
    ax.grid(True, color=CLR_GRID, linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_xlim(0, WINDOW_SIZE)

    # Z ekseninde yatay referans çizgisi (1g yerçekimi)
    if axis_letter == "Z":
        ax.axhline(1.0, color=CLR_SUBTEXT, lw=0.8,
                   linestyle=":", alpha=0.5, label="1g ref")


def make_animator():
    fig, axes, ax_stat = build_figure()

    fig.text(0.5, 0.956,
             "MPU6050 — Ham & Filtreli İvme (g)",
             ha="center", va="top", color=CLR_TEXT,
             fontsize=14, fontweight="bold")

    lines = {}
    for letter, ax in axes.items():
        style_axis(ax, letter)
        h_color = HAM_COLORS[letter]
        f_color = FILT_COLORS[letter]

        ln_h, = ax.plot([], [], color=h_color, lw=1.8,
                        label="Ham  (S1)",
                        solid_capstyle="round")
        ln_f, = ax.plot([], [], color=f_color, lw=1.8,
                        label="Filtreli (S2)",
                        solid_capstyle="round")
        ax.legend(loc="upper right",
                  facecolor=CLR_PANEL, edgecolor=CLR_BORDER,
                  labelcolor=CLR_TEXT, fontsize=8)
        lines[letter] = (ln_h, ln_f)

    # ── Alt durum çubuğu ──────────────────────
    ax_stat.axis("off")
    stat_texts = {}
    stat_cfg = [
        ("HX", "Ham X",      HAM_COLORS["X"],  0.04),
        ("FX", "Filt X",     FILT_COLORS["X"], 0.20),
        ("HY", "Ham Y",      HAM_COLORS["Y"],  0.38),
        ("FY", "Filt Y",     FILT_COLORS["Y"], 0.54),
        ("HZ", "Ham Z",      HAM_COLORS["Z"],  0.72),
        ("FZ", "Filt Z",     FILT_COLORS["Z"], 0.88),
    ]
    for key, label, color, x in stat_cfg:
        ax_stat.text(x, 0.82, label, transform=ax_stat.transAxes,
                     color=CLR_SUBTEXT, fontsize=8, va="center")
        t = ax_stat.text(x, 0.25, "—", transform=ax_stat.transAxes,
                         color=color, fontsize=15, fontweight="bold", va="center")
        stat_texts[key] = t

    conn_dot = ax_stat.text(0.0, 0.25, "●", transform=ax_stat.transAxes,
                             color=CLR_BAD, fontsize=14, va="center")
    conn_lbl = ax_stat.text(0.022, 0.25, "Bağlı değil",
                             transform=ax_stat.transAxes,
                             color=CLR_SUBTEXT, fontsize=8, va="center")
    pkt_lbl  = ax_stat.text(0.99, 0.25, "",
                             transform=ax_stat.transAxes,
                             color=CLR_SUBTEXT, fontsize=8,
                             va="center", ha="right")

    def update(_frame):
        with data_lock:
            if not times:
                return
            xs  = list(range(len(times)))
            snap = {k: list(queues[k]) for k in KEYS}
            lv  = latest.copy()

        all_artists = []
        for letter, ax in axes.items():
            ln_h, ln_f = lines[letter]
            h_data = snap[f"H{letter}"]
            f_data = snap[f"F{letter}"]

            ln_h.set_data(xs, h_data)
            ln_f.set_data(xs, f_data)
            all_artists += [ln_h, ln_f]

            combined = h_data + f_data
            if combined:
                mn, mx = min(combined), max(combined)
                pad = max(0.05, (mx - mn) * 0.20)
                ax.set_ylim(mn - pad, mx + pad)
            ax.set_xlim(0, max(WINDOW_SIZE, len(xs)))

        # Anlık değer kutuları
        for key, t in stat_texts.items():
            t.set_text(f"{lv[key]:+.4f}g")

        # Bağlantı durumu
        if lv["connected"]:
            conn_dot.set_color(CLR_GOOD)
            conn_lbl.set_text(f" {PORT}  {BAUD_RATE} baud")
        else:
            conn_dot.set_color(CLR_BAD)
            conn_lbl.set_text(f" Bağlanılıyor… ({PORT})")

        pkt_lbl.set_text(f"Paket: {lv['pkts']}   Hata: {lv['errs']}")

        return all_artists

    ani = animation.FuncAnimation(
        fig, update,
        interval=80,
        blit=False,
        cache_frame_data=False,
    )
    return fig, ani


# ═══════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Port: {PORT}  |  Baud: {BAUD_RATE}")
    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()
    fig, ani = make_animator()
    print("Grafik açılıyor...\n")
    plt.show()
