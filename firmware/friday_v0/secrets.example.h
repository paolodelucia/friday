// Template for secrets.h. Copy this file to secrets.h (same folder) and
// fill in your real Wi-Fi details there. secrets.h is git-ignored;
// this example file is committed, so keep placeholders in it.
#pragma once

KnownNetwork NETWORKS[] = {
  // Home: use the address server.py prints when you're on The Barn
  { "The Barn",          "YOUR_BARN_PASSWORD",    "http://192.168.2.148:8000" },
  // Campus: your laptop's Mobile Hotspot (Windows always uses 192.168.137.1)
  { "YOUR_HOTSPOT_NAME", "YOUR_HOTSPOT_PASSWORD", "http://192.168.137.1:8000" },
};
