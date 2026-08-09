#!/usr/bin/env python3
"""
Diagnostic: fetch ONE known-good tile from the pwdrmms citizen portal's
vector tile endpoint and decode it, to see:
  - whether it works as a plain unauthenticated request (no cookies/token)
  - what layer(s) and properties the tile actually contains (road name,
    classification, DLP status, etc.)

Confirmed endpoint pattern (found via the portal's own Network tab):
  https://pwdrmms.kerala.gov.in/citizen/kstp-network-sections/{z}/{x}/{y}.mvt

Usage:
    pip install requests mapbox-vector-tile
    python diagnose_pwdrmms_tile.py
"""

import json
import sys

import requests

try:
    import mapbox_vector_tile
except ImportError:
    print("Missing dependency. Install it with:")
    print("    pip install mapbox-vector-tile")
    sys.exit(1)

# The exact tile the user's browser fetched while viewing the map
TILE_URL = "https://pwdrmms.kerala.gov.in/citizen/kstp-network-sections/7/90/60.mvt"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Referer': 'https://pwdrmms.kerala.gov.in/citizen/portal/',
}


def main():
    print("=" * 70)
    print("Fetching known tile (no cookies, no auth token, plain GET):")
    print(TILE_URL)
    print("=" * 70)

    # First: try with NO session/cookies at all - a fresh, cold request.
    r = requests.get(TILE_URL, headers=HEADERS, timeout=20)
    print(f"\nStatus: {r.status_code}")
    print(f"Content-Type: {r.headers.get('Content-Type')}")
    print(f"Content-Length: {len(r.content)} bytes")

    if r.status_code != 200:
        print("\n[!] Non-200 response. Body preview:")
        print(r.text[:500])
        print("\nThis would mean the tile endpoint needs a cookie/session")
        print("from having visited the portal page first, or some other")
        print("auth. Share this output and we'll adjust (e.g. try visiting")
        print("the portal URL first in the same requests.Session() to pick")
        print("up any cookie, then retry the tile request).")
        return

    if not r.content:
        print("\n[!] Got 200 but empty body - unusual, share this output.")
        return

    print("\nDecoding MVT (protobuf) content...")
    try:
        decoded = mapbox_vector_tile.decode(r.content)
    except Exception as e:
        print(f"\n[!] Failed to decode as MVT: {e}")
        print("First 200 bytes (repr):")
        print(repr(r.content[:200]))
        return

    print(f"\nLayers found: {list(decoded.keys())}\n")

    for layer_name, layer_data in decoded.items():
        features = layer_data.get('features', [])
        print(f"--- Layer '{layer_name}': {len(features)} features ---")
        if features:
            sample = features[0]
            print("Sample feature properties:")
            print(json.dumps(sample.get('properties', {}), indent=2))
            geom = sample.get('geometry', {})
            print(f"Sample geometry type: {geom.get('type')}")
            coords = geom.get('coordinates')
            if coords:
                # Coordinates in a raw decoded MVT are in TILE-LOCAL
                # integer units (0-4096 typically), not real lat/lon -
                # that's expected and fine, just noting it here.
                preview = str(coords)[:200]
                print(f"Sample geometry coords (tile-local units): {preview}...")

            # Collect all distinct property KEYS across a sample of features
            # to see what fields are available (road name, class, DLP, etc.)
            all_keys = set()
            for f in features[:200]:
                all_keys.update(f.get('properties', {}).keys())
            print(f"\nAll property keys seen (first 200 features): {sorted(all_keys)}")

            # Print a few more full samples to see variety
            print("\nA few more sample properties:")
            for f in features[1:4]:
                print(" ", json.dumps(f.get('properties', {})))
        print()

    print("=" * 70)
    print("If this worked cleanly, share the printed layer names and")
    print("property keys back - that tells us exactly how to build a full")
    print("extractor (which property marks SH vs MDR, what to use for road")
    print("name, etc.) and whether tile-local coordinates need converting")
    print("(they do - standard slippy-map tile math, which the next script")
    print("will handle automatically).")
    print("=" * 70)


if __name__ == "__main__":
    main()
