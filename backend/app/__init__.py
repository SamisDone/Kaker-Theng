"""Kaker Theng backend."""

import os

# On a server with a fraction of a CPU, library thread pools only fight over
# the quota: there one thread each is faster. The Docker image sets
# KT_THREADS=1; on a normal machine the libraries keep their defaults.
if os.environ.get("KT_THREADS"):
    for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(_var, os.environ["KT_THREADS"])

    import cv2

    cv2.setNumThreads(int(os.environ["KT_THREADS"]))
