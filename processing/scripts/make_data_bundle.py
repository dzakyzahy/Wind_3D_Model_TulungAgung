"""
Menggabungkan wind_data.json, wake_data.json, dan stats_summary.json
menjadi satu file data_bundle.js untuk diload langsung di browser tanpa masalah CORS.
"""
import json, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
VIS_DIR = os.path.join(PROJECT_DIR, 'visualization')

def make_bundle():
    wd_path = os.path.join(VIS_DIR, 'wind_data.json')
    ss_path = os.path.join(VIS_DIR, 'stats_summary.json')
    wk_path = os.path.join(VIS_DIR, 'wake_data.json')
    out_path = os.path.join(VIS_DIR, 'data_bundle.js')

    if not os.path.exists(wd_path):
        print(f"[ERROR] {wd_path} tidak ditemukan!")
        return

    print(f"[INFO] Loading {wd_path}...")
    with open(wd_path, 'r', encoding='utf-8') as f:
        wd = json.load(f)

    ss = None
    if os.path.exists(ss_path):
        print(f"[INFO] Loading {ss_path}...")
        with open(ss_path, 'r', encoding='utf-8') as f:
            ss = json.load(f)

    wk = None
    if os.path.exists(wk_path):
        print(f"[INFO] Loading {wk_path}...")
        with open(wk_path, 'r', encoding='utf-8') as f:
            wk = json.load(f)

    bundle = {
        'windData': wd,
        'statsSummary': ss,
        'wakeData': wk
    }

    print(f"[INFO] Writing {out_path}...")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('window.WIND_DATA_BUNDLE = ' + json.dumps(bundle) + ';\n')
        f.write("console.log('[Data Bundle] Ter-load dengan elev_min_m:', window.WIND_DATA_BUNDLE.windData.meta.elev_min_m);\n")

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"[DONE] data_bundle.js berhasil diperbarui! ({size_mb:.2f} MB)  Elev Min: {wd['meta'].get('elev_min_m')} m")

if __name__ == '__main__':
    make_bundle()
