# Working on FNIRSI 2C53T telemetry

Read README.md for supported firmware, prerequisites and command examples. This repository has its own Git history. Run Git commands from this directory when preparing a change.

## Reader and protocol

Keep CLI behavior in reader/cli.py, packet interpretation in reader/parsed.py and USB selection and requests in reader/transport.py. Offline decoding must remain usable with the Python standard library and without a connected device. Preserve freshness handling and identity verification when changing the live reader. Update docs/parsed-protocol.txt, the firmware and the decoder together when changing the wire format.

Run the following from the repository root for a reader or layout change.

```sh
PYTHONPATH=reader python3 -m unittest discover -s tests -v
python3 reader/cli.py examples/synthetic.fnp
```

## Firmware

The build checks the exact input hash in firmware/build/input-contract.json. Use the offline build and reversal instructions in README.md to check firmware changes with a separately supplied stock image. Record the resulting candidate hash and whether reversal reproduced the input. Report hardware observations separately from offline tests. An offline byte comparison does not verify recovery on the meter.

## Private bench material

In the owner's workspace, local/ contains captures, vendor downloads, research files and the historical patchwork tree used to produce the original bench evidence. Git ignores this directory. Keep private USB serials, raw captures, vendor firmware, generated images and copied reference material out of the public tree. Use synthetic examples in tests. The README embeds a manufacturer-hosted product image and credits its owner.
