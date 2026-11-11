"""Run the Wormhole mailbox and transit relay together on one Machine."""
import os
from pathlib import Path


data_dir = Path(os.environ.get("WORMHOLE_DATA_DIR", "/data"))
data_dir.mkdir(parents=True, exist_ok=True)
os.umask(0o077)

# Fly volumes are mounted as root. Give the service ownership on first boot,
# then run both listeners and create the database as the unprivileged user.
if os.geteuid() == 0:
    os.chown(data_dir, 10001, 10001)
    os.setgroups([])
    os.setgid(10001)
    os.setuid(10001)

from twisted.application.service import Application
from wormhole_mailbox_server import server_tap as mailbox
from wormhole_transit_relay import server_tap as transit


application = Application("wormhole")

mailbox_options = mailbox.Options()
mailbox_options.parseOptions([
    "--port=tcp:4000:interface=0.0.0.0",
    f"--channel-db={data_dir / 'mailbox.sqlite'}",
])
mailbox.makeService(mailbox_options).setServiceParent(application)

transit_options = transit.Options()
transit_options.parseOptions(["--port=tcp:4001:interface=0.0.0.0"])
transit.makeService(transit_options).setServiceParent(application)
