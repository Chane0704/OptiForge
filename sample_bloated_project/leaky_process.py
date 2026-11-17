"""Sample Bloated Process: Simulates a hot loop, memory leak, and file handle leak for profiling."""

import os
import sys
import time

def simulate_bloated_workload():
    print(f"[BloatedProcess] Starting PID {os.getpid()} - simulating memory leak and hot loop...", flush=True)
    leaked_memory_chunks = []
    iteration = 0
    
    # Intentionally hold open a file handle
    dummy_file = open("sample_bloated_project/dummy_leak.tmp", "w")
    dummy_file.write("leak" * 100)
    dummy_file.flush()

    try:
        while iteration < 60:
            iteration += 1
            # 1. Hot loop simulation (tight computation)
            start_t = time.time()
            total = 0
            while time.time() - start_t < 0.15:
                total += 1

            # 2. Memory leak simulation (allocating ~4MB per second continuously)
            chunk = bytearray(2 * 1024 * 1024)  # 2 MB chunk
            leaked_memory_chunks.append(chunk)

            # Minimal sleep to let OS sample
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            dummy_file.close()
            if os.path.exists("sample_bloated_project/dummy_leak.tmp"):
                os.remove("sample_bloated_project/dummy_leak.tmp")
        except Exception:
            pass
        print(f"[BloatedProcess] Terminated PID {os.getpid()}.", flush=True)

if __name__ == "__main__":
    simulate_bloated_workload()
