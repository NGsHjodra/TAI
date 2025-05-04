import asyncio
import os, tempfile
from asyncio import run
from dataclasses import dataclass
from random import randint, choice
from time import time
from threading import Thread


from ipv8.community import Community, CommunitySettings
from ipv8.configuration import ConfigBuilder, Strategy, WalkerDefinition, default_bootstrap_defs
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.peerdiscovery.network import PeerObserver
from ipv8.types import Peer
from ipv8.util import run_forever
from ipv8_service import IPv8
from ipv8.keyvault.crypto import default_eccrypto, ECCrypto
from cryptography.exceptions import InvalidSignature
from ipv8.messaging.serialization import default_serializer
from visualizer import FlaskVisualizer
from visualizer_all import FlaskVisualizerAll


@dataclass
class Transaction(DataClassPayload[1]):
    sender_mid: bytes
    receiver_mid: bytes
    amount: int
    timestamp: float
    signature: bytes
    public_key: bytes

    @classmethod
    def serializer(cls):
        return default_serializer(cls,
            [(bytes, "sender_mid"),
             (bytes, "receiver_mid"),
             (int, "amount"),
             (float, "timestamp"),
             (bytes, "signature"),
             (bytes, "public_key")]
        )
    
#collect all network
@dataclass
class PeerListPayload(DataClassPayload[2]):
    node_id: str 
    connected_peers: str

    @classmethod
    def serializer(cls):
        return default_serializer(cls, [
            ('varlenHutf8', "node_id"),  # Simple string format
            ('varlenHutf8', "connected_peers")  # List of strings format
        ])


def verify_signature(signature: bytes, public_key: bytes, message: bytes) -> bool:
    try:
        pk = default_eccrypto.key_from_public_bin(public_key)
        pk.verify(signature, message)
        return True
    except InvalidSignature:
        return False
    except Exception as e:
        print("Verification error:", e)
        return False

class BlockchainCommunity(Community, PeerObserver):
    community_id = b"myblockchain-test-01"

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.my_key = default_eccrypto.key_from_private_bin(self.my_peer.key.key_to_bin())
        self.known_topology = {
            'nodes': {},
            'connections': []
        }
        self.transactions = []
        self.visualizer = None
        self.connection_keys = set()

    def on_peer_added(self, peer: Peer) -> None:
        print(f"[{self.my_peer.mid.hex()}] connected to {peer.mid.hex()}")

    def on_peer_removed(self, peer: Peer) -> None:
        pass
    
    async def share_peer_list(self):
        while True:
            my_peers = ','.join(p.mid.hex() for p in self.get_peers())

            for peer in self.get_peers():
                try:
                    self.ez_send(peer, PeerListPayload(
                        node_id=self.my_peer.mid.hex(),
                        connected_peers=my_peers
                    ))
                except Exception as e:
                    print(f"Failed to send peer list: {e}")
            await asyncio.sleep(2)

    def started(self) -> None:

        my_id = self.my_peer.mid.hex()
        self.known_topology['nodes'][my_id] = {
            'id': my_id,
            'label': my_id[:6],
            'color': 'green',
            'last_seen': time()
        }
        
        self.network.add_peer_observer(self)
        self.add_message_handler(Transaction, self.on_message)
        self.add_message_handler(PeerListPayload, self.on_peer_list)

        async def send_transaction():
            peers = self.get_peers()
            if not peers:
                return

            receiver = choice(peers)
            amount = randint(1, 100)
            timestamp = time()
            message = (
                self.my_peer.mid +
                receiver.mid +
                amount.to_bytes(4, 'big') +
                str(timestamp).encode()
            )

            signature = default_eccrypto.create_signature(self.my_key, message)

            transaction = Transaction(
                sender_mid=self.my_peer.mid,
                receiver_mid=receiver.mid,
                amount=amount,
                timestamp=timestamp,
                signature=signature,
                public_key=default_eccrypto.key_to_bin(self.my_key.pub())
            )

            self.ez_send(receiver, transaction)
            self.transactions.append({
                'sender': self.my_peer.mid.hex()[:6],
                'receiver': receiver.mid.hex()[:6],
                'amount': amount,
                'timestamp': timestamp
            })

        self.register_task("share_peers", self.share_peer_list)
        self.register_task("send_transaction", send_transaction, interval=5.0, delay=0)

    @lazy_wrapper(PeerListPayload)
    def on_peer_list(self, peer: Peer, payload: PeerListPayload):
        sender_id = payload.node_id
        
        peer_list = payload.connected_peers.split(',')

        self.known_topology['nodes'][sender_id] = {
            'id': sender_id,
            'label': sender_id[:6],
            'color': 'blue',
            'last_seen': time()
        }
        
        for peer_id in peer_list:
            self.known_topology['nodes'][peer_id] = {
                'id': peer_id,
                'label': peer_id[:6],
                'color': 'blue',
                'last_seen': time()
            }
            
            connection_key = tuple(sorted((sender_id, peer_id)))

            if connection_key not in self.connection_keys:
                self.connection_keys.add(connection_key)
                self.known_topology['connections'].append({
                    'source': sender_id,
                    'target': peer_id,
                    'last_updated': time()
                })

    @lazy_wrapper(Transaction)
    def on_message(self, peer: Peer, payload: Transaction) -> None:
        message = (
            payload.sender_mid +
            payload.receiver_mid +
            payload.amount.to_bytes(4, 'big') +
            str(payload.timestamp).encode()
        )

        if not verify_signature(payload.signature, payload.public_key, message):
            print(f"[{self.my_peer}] ❌ Invalid TX from {peer}")
            return

        print(f"[{self.my_peer}] ✅ TX from {payload.sender_mid.hex()} → {payload.receiver_mid.hex()} amount={payload.amount}")
        self.transactions.append({
            'sender': payload.sender_mid.hex()[:6],
            'receiver': payload.receiver_mid.hex()[:6],
            'amount': payload.amount,
            'timestamp': payload.timestamp
        })


def start_node(developer_mode, visualizer_port=None, is_main_run=False):
    async def boot():
        builder = ConfigBuilder().clear_keys().clear_overlays()
        crypto = ECCrypto()
        my_key = crypto.generate_key("medium")
        key_bin = my_key.key_to_bin()
        if developer_mode == True:
            print("-----------------")
            print("Builder, crypto, key and binary key locked in")

        with tempfile.NamedTemporaryFile(delete=False, mode='wb', suffix='.pem') as f:
            f.write(key_bin)
            key_path = f.name
        if developer_mode == True:
            print("Temporary file generated")

        port_offset = int(os.environ.get("PORT_OFFSET", "0"))
        port = 8091 + port_offset
        if developer_mode == True:
            print(f"Port set at {port}")

        generation_status = "medium"
        alias_status = "my peer"
        builder.add_key(alias_status, generation_status, key_path)
        builder.set_port(port)
        if developer_mode == True:
            print(f"Builder set at port {port}, generation status of '{generation_status}' and alias status of '{alias_status}'")

        builder.add_overlay("BlockchainCommunity", "my peer",
                          [WalkerDefinition(Strategy.RandomWalk, 10, {'timeout': 3.0})],
                          default_bootstrap_defs, {}, [('started',)])

        ipv8 = IPv8(builder.finalize(), extra_communities={'BlockchainCommunity': BlockchainCommunity})
        await ipv8.start()
        
        # Start visualizer if port is specified
        if visualizer_port is not None:
            community = ipv8.get_overlay(BlockchainCommunity)
            community.visualizer = FlaskVisualizer(community, port=visualizer_port)
            # Start the visualizer asynchronously so it doesn't block the main event loop
            Thread(target=community.visualizer.start).start()

        if not is_main_run:
            main_viz = FlaskVisualizerAll(community=community, port=8080)
            main_viz.start()
        
        await run_forever()

    run(boot())