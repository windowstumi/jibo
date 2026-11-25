# Live2D experiment tools

This is the portable version of the previously tested character workflow. It is
separate from jibo's production 2.5D renderer. Installing it does not switch the
desktop client's renderer or automatically import a character.

Windows x64: `setup.cmd -WithLive2D` installs dependencies and the official
PSD2Live 3.8.4 portable distribution under `.runtime/`. Python and Node are also
project-local; no `D:\AI-Live-Demos` installation is needed.

```
live2d.cmd -Mode doctor
live2d.cmd -Mode generate -Source "C:\images\reference.png" -Workspace "data\my-character" -ApiBase "https://your-service/v1"
live2d.cmd -Mode build -Workspace "data\my-character" -Profile "path\calibrated-profile.json"
live2d.cmd -Mode preview -Workspace "data\my-character"
```

Generation makes up to six paid image-edit requests. The key is read from a
hidden terminal prompt or `IMAGE_API_KEY`, never written to the manifest. Failed
or interrupted requests are not automatically resubmitted; verify the provider's
history before deciding to retry. Successful files are reused.

**A profile is required for building.** `profiles/silver-hair.json` records the
manually calibrated masks and shoulder/elbow/wrist locations of the silver-haired
example. It must be recalibrated for a different image, even at the same resolution.
This tool does not claim reliable single-image automatic semantic segmentation.

Build uses the official PSD2Live command line for the base model, then its local
MCP API for the editable shoulder/elbow/wrist chains and motion clips. It starts
the project-local editor if needed. Save an already-open editor project before
building: the tool deliberately refuses to discard unsaved work.
On a new Windows user account, enable the editor's MCP service in Settings if
the connection check requests it; the build test reused an already enabled
local editor service. The desktop client itself does not require this service.

Outputs include the layered PSD, editable `.psd2live` and `.cmo3`, distributable
`.moc3`/textures/motions, and GIF previews. The generated preview runs locally and
does not need a third-party web CDN. The scripts do not bundle Cubism's proprietary
web runtime, model weights, generated artwork, original reference images or API
credentials in Git. PSD2Live is downloaded from its official release; see its
[license and source](https://github.com/tsunehimatoi/psd2live).

`mcp_proxy.py` is the upstream PSD2Live compatibility client, retained with its
documentation. The other scripts implement this project's experiment.
