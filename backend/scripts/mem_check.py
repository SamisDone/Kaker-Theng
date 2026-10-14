"""Peak memory for one session: three page photos, then the font.

    docker run --rm -m 512m --memory-swap 512m -e PYTHONPATH=/srv \
      -v <folder with {mode}-p{1,2,3}.jpg>:/data -v <backend>/scripts:/s \
      kaker-theng-backend python /s/mem_check.py colour /data
"""

import resource, sys, time

def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

def cgroup_peak_mb():
    for path in ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
        try:
            return int(open(path).read()) / 2**20
        except OSError:
            pass
    return float("nan")

mode, folder = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "/data")
t0 = time.time()
from app.pipeline import decode_image, process_page
from app.fontbuild import build_font
from app.glyphmap import build_layout
build_layout()
steps = [f"startup {peak_mb():.0f} MB"]
drawings = []
for page in (1, 2, 3):
    data = open(f"{folder}/{mode}-p{page}.jpg", "rb").read()
    r = process_page(decode_image(data), page)
    drawings += r.drawings
    del r
    steps.append(f"p{page} {peak_mb():.0f} MB")
font = build_font(drawings, "Memory Check")
steps.append(f"font {peak_mb():.0f} MB")
print(f"{mode:<10} peak RSS {peak_mb():.0f} MB | container peak {cgroup_peak_mb():.0f} MB | {time.time() - t0:.0f} s | " + ", ".join(steps))
