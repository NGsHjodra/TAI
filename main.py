from multiprocessing import Process
import os
from single_node import start_node

NUM_PEERS = 4

def run_peer(port_offset):
    dev_mode = True
    os.environ["PORT_OFFSET"] = str(port_offset)
    visualizer_port = 8080 + port_offset
    start_node(dev_mode, visualizer_port=visualizer_port)

if __name__ == "__main__":
    processes = []
    for i in range(NUM_PEERS):
        p = Process(target=run_peer, args=(i,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
