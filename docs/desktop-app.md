# Desktop app for Windows and Mac (pilot)

The desktop app runs Sonos Analyzer on a laptop with no Docker and nothing else to install: download it, open it, and it opens the analyzer in your browser. Speaker discovery works too, so you usually don't need to type an IP address.

> **This is a pilot.** The builds are not yet signed by a verified publisher, so Windows and macOS warn you before opening them the first time. The steps below show how to get past each warning. If you'd rather not, [run it from source with Python](#run-from-source-with-python) or use the [Docker Desktop guide](docker-desktop.md) instead.

The app only reads diagnostics from the speakers. It never changes a Sonos setting, needs no Sonos account, and the page is only reachable from your own laptop.

## Choose how to run it

The ready-made app is there for convenience. Every option runs the same open-source code, and two of them let you read that code before running anything:

| Option | What you run | Can you inspect the code first? | Discovery |
|---|---|---|---|
| **Ready-made app** (this page) | A downloaded `.exe` or Mac app | It's built automatically from the published source, but the file itself is compiled | Works |
| **[Run from source with Python](#run-from-source-with-python)** | The Python files themselves, which you can open and read | Yes: what you read is exactly what runs | Works |
| **[Docker Desktop, inspect-the-code route](docker-desktop.md#inspect-the-code-route-build-it-yourself)** | A container you build yourself from the source | Yes | Type a speaker IP |

If you'd rather not run a compiled file from the internet, or your company doesn't allow unsigned apps, use one of the inspectable options; they give the same results.

## Download

Pilot version 0.4.0 beta 1. Select the file for your computer to download it:

| Computer | Download |
|---|---|
| Windows 10 or 11 | [SonosAnalyzer-0.4.0-beta.1-windows-x64.exe](https://github.com/grahamfairbank/sonos-analyzer/releases/download/v0.4.0-beta.1/SonosAnalyzer-0.4.0-beta.1-windows-x64.exe) (about 10 MB) |
| Mac with Apple silicon (M1 or later) | [SonosAnalyzer-0.4.0-beta.1-macos-apple-silicon.zip](https://github.com/grahamfairbank/sonos-analyzer/releases/download/v0.4.0-beta.1/SonosAnalyzer-0.4.0-beta.1-macos-apple-silicon.zip) |
| Mac with an Intel processor | [SonosAnalyzer-0.4.0-beta.1-macos-intel.zip](https://github.com/grahamfairbank/sonos-analyzer/releases/download/v0.4.0-beta.1/SonosAnalyzer-0.4.0-beta.1-macos-intel.zip) (about 9 MB) |

To check which Mac you have: Apple menu > **About This Mac**. "Chip: Apple M…" means Apple silicon; "Processor: Intel…" means Intel.

These links are for this pilot version; newer versions are listed on the [releases page](https://github.com/grahamfairbank/sonos-analyzer/releases), under **Assets**.

## Windows

1. Your browser may say the file "isn't commonly downloaded". Choose **Keep** (in Edge: **…** > **Keep**, then **Show more** > **Keep anyway**).
2. Double-click `SonosAnalyzer-…-windows-x64.exe`.
3. If **Windows protected your PC** appears, select **More info**, then **Run anyway**. You only need to do this once per version.
4. A black window opens showing "Sonos Analyzer … is running", and the analyzer opens in your browser.
5. If Windows Firewall asks whether to allow access, choose **Allow** for private networks. If you cancel, discovery may not find the speakers; type a speaker's IP address instead.

To stop it, select **Quit Sonos Analyzer** on the page, or close the black window.

## Mac

1. Open the downloaded `.zip` file. (Safari usually unzips it for you.) You get **Sonos Analyzer**. You can drag it to Applications, but you don't have to.
2. Double-click **Sonos Analyzer**. macOS stops it the first time:
   - **macOS 15 (Sequoia) and later:** a message says it was not opened. Choose **Done**. Open **System Settings** > **Privacy & Security**, scroll down to **Security**, and select **Open Anyway** next to the Sonos Analyzer message. Enter your password, then select **Open Anyway** again.
   - **macOS 14 (Sonoma) and earlier:** Control-click (or right-click) **Sonos Analyzer**, choose **Open**, then **Open** again.
3. The analyzer opens in your browser. The app has no window or Dock icon of its own; the browser page is the app.
4. When macOS asks to **find devices on local networks**, choose **Allow**. Without it the app cannot reach the speakers. If you chose Don't Allow, turn it on in **System Settings** > **Privacy & Security** > **Local Network**.

To stop it, select **Quit Sonos Analyzer** on the page. If you just close the tab, the app stops by itself after 15 minutes.

## Scan

1. Select **Scan network**. Leave the IP box empty; the app finds the speakers itself. A scan takes about 10 seconds.
2. If it says no speakers were discovered, type one speaker's IP address into **Speaker IPs** and scan again. In the Sonos app, find it under **Settings** > **Manage** (next to **My System**) > **About My System**.
3. Use **Download JSON** or **Download HTML** to save the results.

The laptop must be on the same network as the speakers: the same Wi-Fi (not a guest network), with any VPN turned off.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Browser doesn't open | Open `http://127.0.0.1:8400` yourself. If another program uses port 8400, the app picks the next free port (8401, 8402…); on Windows, the black window shows the address. |
| "No Sonos speakers discovered" | Type one speaker's IP address and scan again. On a Mac, check **Local Network** access is on (see above). |
| "Could not read diagnostics from any speaker" | The laptop cannot reach the speakers: check it's on the same network, not a guest Wi-Fi, and that any VPN is off. |
| Antivirus quarantines the Windows file | Unsigned apps built this way are sometimes flagged by mistake. Restore it if you trust the source, or [run it from source with Python](#run-from-source-with-python) instead. |
| Mac says the app "is damaged and can't be opened" | Some download tools trigger this for unsigned apps. [Run it from source with Python](#run-from-source-with-python) for now, and please report it. |

## Run from source with Python

This runs exactly the same app as the download, from Python files you can read first. It needs Python 3.10 or later and nothing else.

1. **Install Python** if you don't have it:
   - **Windows:** install it from [python.org/downloads](https://www.python.org/downloads/) and tick **Add python.exe to PATH** in the installer.
   - **Mac:** install it from [python.org/downloads](https://www.python.org/downloads/).
2. **Get the source:** open [github.com/grahamfairbank/sonos-analyzer](https://github.com/grahamfairbank/sonos-analyzer), select **Code** > **Download ZIP**, and extract it. Or, with Git:

   ```bash
   git clone https://github.com/grahamfairbank/sonos-analyzer
   ```

3. **Read it.** The application is the `sonos_analyzer` folder, standard-library Python only. `fetch.py` holds every request made to the speakers (plain HTTP reads on port 1400), and `app.py` is what starts when you open the app.
4. **Run it** from a terminal in the extracted `sonos-analyzer` folder:
   - **Windows:** `py -m sonos_analyzer.app`
   - **Mac:** `python3 -m sonos_analyzer.app`

   The analyzer opens in your browser, just like the downloaded app. On a Mac, allow **Terminal** to find devices on local networks if asked. Press Ctrl+C in the terminal, or **Quit** on the page, to stop it.

## How the ready-made app is built

The download is this same Python code bundled with its own copy of Python by [PyInstaller](https://pyinstaller.org/). GitHub Actions builds it from the release's tagged source for Windows, Apple-silicon Macs and Intel Macs, checks that each build starts, and attaches the files to the release. The [build workflow](../.github/workflows/desktop-build.yml) and every [build log](https://github.com/grahamfairbank/sonos-analyzer/actions/workflows/desktop-build.yml) are public.

## Pilot feedback

Please [open a GitHub issue](https://github.com/grahamfairbank/sonos-analyzer/issues/new) and include:

- Windows or macOS, and its version
- Which warnings appeared, and whether the steps above got you past them
- Whether discovery found the speakers, or you had to type an IP address
- Anything confusing, and the JSON report if a result looks wrong (remove anything you'd rather not share)
