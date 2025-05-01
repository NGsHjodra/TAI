from multiprocessing import Process
import os
from single_node import start_node

NUM_PEERS = 5

def run_peer(port_offset):
    os.environ["PORT_OFFSET"] = str(port_offset)
    start_node()

if __name__ == "__main__":
    processes = []
    for i in range(NUM_PEERS):
        p = Process(target=run_peer, args=(i,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()