from multiprocessing import Process
import os
from single_node import start_node
from threading import Thread
from visualizer_all import FlaskVisualizerAll

NUM_PEERS = 4

def run_peer(port_offset, is_main_run):
    dev_mode = True
    os.environ["PORT_OFFSET"] = str(port_offset)
    visualizer_port = 8081 + port_offset
    start_node(dev_mode, visualizer_port=visualizer_port, is_main_run = is_main_run)

if __name__ == "__main__":
    is_main_run = False
    processes = []
    for i in range(NUM_PEERS):
        p = Process(target=run_peer, args=(i, is_main_run))
        p.start()
        processes.append(p)
        is_main_run = True

    for p in processes:
        p.join()
