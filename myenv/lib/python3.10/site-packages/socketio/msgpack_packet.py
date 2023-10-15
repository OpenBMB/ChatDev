import msgpack
from . import packet


class MsgPackPacket(packet.Packet):
    uses_binary_events = False

    def encode(self):
        """Encode the packet for transmission."""
        return msgpack.dumps(self._to_dict())

    def decode(self, encoded_packet):
        """Decode a transmitted package."""
        decoded = msgpack.loads(encoded_packet)
        self.packet_type = decoded['type']
        self.data = decoded.get('data')
        self.id = decoded.get('id')
        self.namespace = decoded['nsp']
