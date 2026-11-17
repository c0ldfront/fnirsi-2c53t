# FNIRSI 2C53T USB telemetry

Read the multimeter display of a FNIRSI 2C53T over USB as newline-delimited JSON. This independent, experimental project includes a Python reader, a synthetic capture, and the source of the telemetry extension for one specific V1.0.7 application image. Live readings require a meter already running the compatible experimental firmware.

<img src="https://www.fnirsi.com/cdn/shop/files/fnirsi-2c53t-50mhz-250mss-handheld-3in1-oscilloscope-multimeter-signal-generatordigital-oscilloscopefnirsifnirsi-3601941.jpg?v=1751709903&amp;width=600" width="320" alt="FNIRSI 2C53T handheld meter showing its display, keypad and four measurement jacks">

Product image © FNIRSI Technology Co., Ltd. [Manufacturer’s product page](https://www.fnirsi.com/products/2c53t)

## Repository layout

| Directory | Contents |
| --- | --- |
| [reader](reader/) | Python CLI, packet decoder and USB transport |
| [firmware](firmware/) | Meter-side payload, stock adapter, USB transport, layout header and reproducible build |
| [tests](tests/) | Offline decoder, transport and CLI tests |
| [examples](examples/) | Synthetic capture for trying the reader |
| [docs](docs/) | Packet format and display-unit mapping |
| [tools](tools/) | Offline patch application and reversal |

## Try the reader offline

Run these commands from the repository root with Python 3.10 or later. Offline decoding uses the Python standard library.

```sh
python3 reader/cli.py examples/synthetic.fnp
PYTHONPATH=reader python3 -m unittest discover -s tests -v
```

Each output line describes one poll. The first packet establishes a baseline. A subsequent fresh numeric sample includes its value and unit. Status-only, stale, and busy packets have no usable numeric value. See the [packet format](docs/parsed-protocol.txt).

## Read a compatible meter

On Linux, use PyUSB with a libusb backend and grant your user access to the meter's current USB device node. In multimeter mode, the following command polls the tested USB identifiers ten times. The reader checks the firmware protocol identity before accepting a sample.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pyusb==1.3.1
.venv/bin/python reader/cli.py --live --vid 0x2e3c --pid 0x5720 --count 10
```

When multiple meters match, pass the desired device's serial with `--serial`. The CLI uses device-to-host telemetry requests. Firmware-upgrade mode and factory USB Sharing serve different purposes.

## Reproduce the experimental build offline

Use your own original V1.0.7 application file. The build checks for 486720 bytes and SHA-256 `83271baa03bcbf15200cfb80fa92a8cd0d7c37889b088d382098dcd2c9e0d2b3`. The repository includes project source and a version-specific input contract. Vendor firmware and completed images are excluded.

On Linux with GNU Make, Bash, GNU coreutils, Python 3 and GNU Arm Embedded GCC/binutils on PATH, run the following in a fresh output directory.

```sh
cd firmware/build
stock=/absolute/path/to/APP_2C53T_V1.0.7_241205.bin
make STOCK="$stock" OUT=out-local
python3 plan.py --build . --artifacts out-local --stock "$stock" --output out-local/plan.json
python3 ../../tools/patch.py "$stock" out-local/plan.json --output out-local/candidate.bin
python3 ../../tools/patch.py out-local/candidate.bin out-local/plan.json --reverse --output out-local/reversed.bin
cmp "$stock" out-local/reversed.bin
```

The final comparison checks byte-exact reversal on disk. Device recovery, calibration preservation, other firmware versions and other hardware revisions remain unverified. One experimental meter produced USB readings including 3.542 V while its operator reported 3.541–3.542 V on screen. That observation establishes display agreement for one reading. It does not establish measurement accuracy or general firmware reliability.

## License

The project's original source and documentation are distributed under the [MIT License](LICENSE). FNIRSI is the instrument manufacturer's name. This is a community project.
