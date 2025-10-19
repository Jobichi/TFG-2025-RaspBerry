#!/usr/bin/env python3
import asyncio
from ari_client import ARIClient

if __name__ == "__main__":
    try:
        asyncio.run(ARIClient().run())
    except KeyboardInterrupt:
        pass
