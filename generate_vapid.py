import base64
from cryptography.hazmat.primitives.asymmetric import ec

def b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
key=ec.generate_private_key(ec.SECP256R1())
priv=key.private_numbers().private_value.to_bytes(32,'big')
pub=key.public_key().public_bytes(__import__('cryptography').hazmat.primitives.serialization.Encoding.X962,__import__('cryptography').hazmat.primitives.serialization.PublicFormat.UncompressedPoint)
print('VAPID_PUBLIC_KEY='+b64(pub))
print('VAPID_PRIVATE_KEY='+b64(priv))
print('VAPID_EMAIL=mailto:your-email@example.com')
