# Non-native runtime

Non-native packages repack the verified upstream binary payload and do not
compile FreeCAD. The normalized runtime is installed under `/opt/<package>`:

- `/opt/freecad-non-native/`
- `/opt/freecad-candidate-non-native/`

The launcher sets package-specific `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and
`FREECAD_USER_HOME`. The Linux kernel, ELF loader, glibc ABI, graphics drivers,
and desktop interfaces still come from the host; application libraries remain
in the bundled runtime.

## User installation

Download and extract the matching verified payload artifact from a successful
workflow run, then point the installer at its normalized payload directory:

```sh
PKG=freecad-non-native PAYLOAD_DIR=/path/to/payload-x86_64 ./scripts/install-user.sh
```

The installer checks the package identity and architecture in
`payload-manifest.json`, installs under `~/.local/opt/<package>`, and creates a
package-specific launcher and desktop entry. Set `ARCH=aarch64` when installing
an aarch64 payload on an aarch64 host if automatic architecture detection is
not suitable.

Uninstalling removes the selected runtime and its launcher. User settings and
data are kept by default; set `PURGE_DATA=1` with `scripts/uninstall-user.sh` to
remove those directories too.
