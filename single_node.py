import tempfile
import os
from asyncio import run
from dataclasses import dataclass
from random import randint, choice
from time import time

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
from ipv8.messaging.payload import default_dataclass_serializer



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
        return default_dataclass_serializer([
            (bytes, "sender_mid"),
            (bytes, "receiver_mid"),
            (int, "amount"),
            (float, "timestamp"),
            (bytes, "signature"),
            (bytes, "public_key"),
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


class MyCommunity(Community, PeerObserver):
    community_id = b"myblockchain-test-01"

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.my_key = default_eccrypto.key_from_private_bin(self.my_peer.key.key_to_bin())

    def on_peer_added(self, peer: Peer) -> None:
        print(f"[{self.my_peer.mid.hex()}] connected to {peer.mid.hex()}")

    def on_peer_removed(self, peer: Peer) -> None:
        pass

    def started(self) -> None:
        self.network.add_peer_observer(self)
        self.add_message_handler(Transaction, self.on_message)

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

        self.register_task("send_transaction", send_transaction, interval=5.0, delay=0)

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


def start_node():
    async def boot():
        builder = ConfigBuilder().clear_keys().clear_overlays()
        crypto = ECCrypto()
        my_key = crypto.generate_key("medium")
        key_bin = my_key.key_to_bin()

        with tempfile.NamedTemporaryFile(delete=False, mode='wb', suffix='.pem') as f:
            f.write(key_bin)
            key_path = f.name

        port_offset = int(os.environ.get("PORT_OFFSET", "0"))
        port = 8090 + port_offset

        builder.add_key("my peer", "medium", key_path)
        builder.set_port(port)

        builder.add_overlay("MyCommunity", "my peer",
                            [WalkerDefinition(Strategy.RandomWalk, 10, {'timeout': 3.0})],
                            default_bootstrap_defs, {}, [('started',)])

        ipv8 = IPv8(builder.finalize(), extra_communities={'MyCommunity': MyCommunity})
        await ipv8.start()
        await run_forever()

    run(boot())