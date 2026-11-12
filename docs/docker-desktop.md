# Run Sonos Analyzer on a laptop with Docker Desktop

This guide is for running Sonos Analyzer on a Windows or Mac laptop, without a server. The analyzer only reads diagnostics from the speakers. It never changes a Sonos setting, and it needs no Sonos account.

There are two ways to run it. Both end up with the same page at `http://localhost:8400`:

| | **Easy route: ready-built image** | **Inspect-the-code route: build it yourself** |
|---|---|---|
| Best for | Most people | Anyone who wants to read or check the code first, or change it |
| What you do | Paste one command | Download the source, then build and start it with one command |
| Needs | Docker Desktop | Docker Desktop, plus the source code (ZIP or Git) |
| Time after Docker Desktop is installed | About a minute | A few minutes |

The ready-built image is made automatically by GitHub from the published source for each release (see [Where the ready-built image comes from](#where-the-ready-built-image-comes-from)), so both routes run the same code.

**Contents:** [Before you start](#before-you-start) · [Install Docker Desktop](#install-docker-desktop) · [Easy route](#easy-route-ready-built-image) · [Inspect-the-code route](#inspect-the-code-route-build-it-yourself) · [Scan](#scan) · [Day-to-day](#day-to-day) · [Troubleshooting](#troubleshooting) · [Without Docker](#without-docker)

## Before you start

- **A Windows 10/11 or macOS laptop** (Intel or Apple silicon) with administrator rights to install software.
- **The laptop on the same network as the speakers.** Connect to the same Wi-Fi as the Sonos system, not a guest network, and turn off any VPN while you scan.
- **One speaker's IP address.** In the Sonos app, go to **Settings**, select **Manage** next to **My System**, then **About My System**, and note any IP address listed. ([Sonos support: About My System](https://support.sonos.com/en-us/article/check-system-information-in-about-my-system)) Your router's list of connected devices shows them too. One address is enough; the analyzer finds the rest of the system from it.

> **Licensing:** Docker Desktop is free for personal use, education and small businesses, but larger organizations need a paid Docker subscription. Check [Docker's licensing terms](https://www.docker.com/pricing/faq/) or with your IT team before installing it on a company laptop. If Docker Desktop is not an option, see [Without Docker](#without-docker).

## Install Docker Desktop

1. Download Docker Desktop from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) and run the installer. On Windows, accept the default of using WSL 2.
2. Start Docker Desktop and wait until it reports that the engine is running (a green status at the bottom left of its window).
3. Signing in to a Docker account is not needed; you can skip it.

Both routes need one command typed into a terminal. To open one:

- **Windows:** right-click the Start button and select **Terminal** (or **Windows PowerShell**).
- **Mac:** open **Terminal** from Applications > Utilities.

## Easy route: ready-built image

Paste this into the terminal and press Enter:

```bash
docker run -d --name sonos-analyzer -p 127.0.0.1:8400:8400 --restart unless-stopped ghcr.io/grahamfairbank/sonos-analyzer:latest
```

Docker downloads the image (about 45 MB) and starts it. It then appears as **sonos-analyzer** in the **Containers** list in Docker Desktop, where you can stop, start and delete it without the terminal.

Now go to [Scan](#scan).

## Inspect-the-code route: build it yourself

1. **Get the source.** Either:
   - open [github.com/grahamfairbank/sonos-analyzer](https://github.com/grahamfairbank/sonos-analyzer), select **Code**, then **Download ZIP**, and extract it, for example to your Documents folder; or
   - with Git:

     ```bash
     git clone https://github.com/grahamfairbank/sonos-analyzer
     ```

2. **Read whatever you like.** The application is the `sonos_analyzer` folder, written in Python with no third-party packages. `fetch.py` contains every request made to the speakers (plain HTTP reads on port 1400), and the `Dockerfile` shows exactly how the image is built.

3. **Build and start it.** Open a terminal in the `sonos-analyzer` folder (the one that contains `docker-compose.desktop.yml`):
   - **Windows:** open the folder in File Explorer, right-click an empty area, and select **Open in Terminal**.
   - **Mac:** in Terminal, type `cd ` (with a trailing space), drag the folder onto the Terminal window, and press Return.

   Then run:

   ```bash
   docker compose -f docker-compose.desktop.yml up -d --build
   ```

   The first build takes a minute or two. The container then appears as **sonos-analyzer** in Docker Desktop's **Containers** list.

## Scan

1. Open [http://localhost:8400](http://localhost:8400) in your browser.
2. Type the speaker IP address from [Before you start](#before-you-start) into **Speaker IPs**.
3. Select **Scan network**. A scan takes about 10 seconds.

Leaving the IP box empty does not work under Docker Desktop. Automatic discovery relies on network multicast, which does not pass through Docker Desktop's virtual machine, so you get "No Sonos speakers discovered".

Use **Download JSON** or **Download HTML** to save the results, for example to attach to a support case.

The page is only reachable from the laptop itself (`127.0.0.1`), because it has no login. Keep it that way on customer and public networks.

## Day-to-day

Stopping, starting and removing work the same for both routes from the **Containers** list in Docker Desktop. The container starts again by itself whenever Docker Desktop starts, until you stop it, so stop it when you're done if you don't want it running.

| Task | Easy route (terminal) | Inspect-the-code route (terminal, in the `sonos-analyzer` folder) |
|---|---|---|
| Stop | `docker stop sonos-analyzer` | `docker compose -f docker-compose.desktop.yml down` |
| Start again | `docker start sonos-analyzer` | `docker compose -f docker-compose.desktop.yml up -d` |
| Update to the latest version | `docker rm -f sonos-analyzer`, `docker pull ghcr.io/grahamfairbank/sonos-analyzer:latest`, then the [run command](#easy-route-ready-built-image) again | Download the latest ZIP (or `git pull`), then `docker compose -f docker-compose.desktop.yml up -d --build` |
| Remove completely | `docker rm -f sonos-analyzer` and `docker rmi ghcr.io/grahamfairbank/sonos-analyzer:latest` | `docker compose -f docker-compose.desktop.yml down --rmi local` |

## Troubleshooting

| Message or symptom | What to check |
|---|---|
| "No Sonos speakers discovered" | Expected under Docker Desktop. Type a speaker IP address and scan again. |
| "Could not read diagnostics from any speaker" | The laptop cannot reach the speakers. Check it is on the same network (not a guest or isolated Wi-Fi), that any VPN is off, and that the IP address is correct. A quick check: opening `http://<speaker-ip>:1400/status` in the browser should show a page. |
| The page at `localhost:8400` does not load | Check Docker Desktop is running and **sonos-analyzer** shows as running. If another program uses port 8400, use another port: in the easy route change `127.0.0.1:8400:8400` to `127.0.0.1:8401:8400`; in the inspect-the-code route change the first `8400` in `docker-compose.desktop.yml`. Then open `http://localhost:8401`. |
| "The container name "/sonos-analyzer" is already in use" | It is already installed. Start it from Docker Desktop, or remove it first with `docker rm -f sonos-analyzer`. |
| `docker: command not found` or "cannot connect to the Docker daemon" | Docker Desktop is not installed or not started. Start it and wait for the engine to show as running. |
| The download or build fails | The laptop needs internet access the first time. Corporate proxies may need configuring under Docker Desktop **Settings > Resources > Proxies**. |

## Where the ready-built image comes from

Each release is tagged in GitHub, and a [GitHub Actions workflow](../.github/workflows/docker-publish.yml) builds the image from that tagged source and publishes it to GitHub Container Registry for Intel/AMD and ARM computers. You can see every build under the repository's [Actions tab](https://github.com/grahamfairbank/sonos-analyzer/actions), and the image records the exact commit it was built from:

```bash
docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' ghcr.io/grahamfairbank/sonos-analyzer:latest
```

To run a specific release instead of the newest, replace `latest` with its version number, for example `ghcr.io/grahamfairbank/sonos-analyzer:0.3.0`.

## Optional: automatic discovery with host networking

Docker Desktop 4.34 and later has an optional host networking mode (**Settings > Resources > Network > Enable host networking**; it requires signing in to a Docker account). Docker documents it as working for TCP and UDP traffic, but not whether it passes the multicast that discovery needs, and this has not been tested with Sonos Analyzer. Typing a speaker IP address is the supported route. ([Docker: host network driver](https://docs.docker.com/engine/network/drivers/host/))

## Without Docker

If Docker Desktop isn't available, the analyzer also runs directly with Python 3.10 or later, which needs no other packages. Running it this way, automatic discovery works too. From the source folder ([Inspect-the-code route](#inspect-the-code-route-build-it-yourself), step 1):

```bash
cd sonos-analyzer
python -m sonos_analyzer.web --port 8400
```

Then open [http://localhost:8400](http://localhost:8400). On Windows, use `py` instead of `python` if `python` is not found.

## Tested so far

Both routes, with a typed IP address (the setup this guide uses), have been tested on Linux against a 19-speaker S2 system. Docker Desktop on Windows and macOS uses the same networking but has not been verified yet. Reports from either are welcome as [GitHub issues](https://github.com/grahamfairbank/sonos-analyzer/issues).
