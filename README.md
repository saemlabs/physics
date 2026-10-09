🎬 Vertical Physics Shorts Engine: Automated 3b1b + Feynman Production Pipeline
An automated, serverless production pipeline designed to transform raw conceptual physics ideas and JEE entrance exam questions into high-definition 9:16 vertical video shorts.
By pairing 3Blue1Brown-style vector animations with Feynman-inspired conceptual narration and zero-shot AI voice cloning, this engine automates video generation from a single CSV spreadsheet using GitHub Actions.
🏛️ Vision & Core Philosophy
 * Intuition First, Formulas Second: Rooted in Richard Feynman's teaching style, every video starts with visual primitives (vector fields, symmetry, charge interactions, light refraction) before deriving mathematical formulas.
 * 3Blue1Brown Visual Rigor: Powered by the Manim animation engine, complex concepts are visualized using clean geometric layouts, vector fields, coordinates, and animated math cards.
 * Zero-Touch Automated Scale: Content creators write plain-text scripts and visual specs in a CSV file. The CI/CD pipeline handles audio cloning, scene rendering, audio-video stitching, and artifact bundling automatically.
🏗️ Architecture Overview
 ┌──────────────────┐
 │ content_batch.csv│  ◄── Single Source of Truth (Scripts, LaTeX, Visual JSON)
 └─────────┬────────┘
           │
           ▼
 ┌──────────────────┐
 │ batch_runner.py  │  ◄── Orchestrates pipeline & handles parallel sharding
 └────┬────────┬────┘
      │        │
      │        ├───► ┌───────────────────┐
      │        │     │ generate_audio.py │ ──► Synthesizes voice (Coqui XTTS-v2) & pad
      │        │     └───────────────────┘
      │        │
      │        └───► ┌─────────────────────┐
      │              │ render_universal.py │ ──► Renders 9:16 Manim visual scene
      │              └─────────────────────┘
      │
      ▼
 ┌──────────────────┐
 │  FFmpeg Engine   │  ◄── Mixes audio tracks, applies fade, and stitches MP4
 └─────────┬────────┘
           │
           ▼
 ┌──────────────────┐
 │  GitHub Actions  │  ◄── Executes 4-worker matrix parallel build in the cloud
 └──────────────────┘

📑 File-by-File Technical Deep Dive
1. content_batch.csv — The Data Model
The single source of truth driving the entire video catalog without modifying codebase logic.
 * Feynman Narration Scripts: Plain-text scripts optimized for natural speech synthesis and paced conceptual explanations.
 * Declarative Visual JSON: High-level specifications for geometric primitives (charges, lines, vectors, arcs, lenses, function graphs) rendered dynamically by Manim.
 * Structured JEE PYQs: Multi-column layout supporting question text, four options, correct answer highlighting, and LaTeX derivation steps.
2. render_universal.py — The Master Animation Engine
A dynamic 9:16 vertical rendering engine built on top of Manim.
 * Vertical Spatial Zoning: Divides the 1080x1920 canvas into 6 precise vertical layout zones (Header, Question, Visual Scene, Options, Equation Cards, Answer Box) to prevent element overlap.
 * Declarative JSON Compiler: Translates raw JSON specifications into animated Manim mobjects (Field, Charge, Vector, Arc, Lens, Graph).
 * Deferred Rotation Engine: Solves spatial origin bugs by tracking element rotators and executing pivot animations after global center alignment.
 * Unicode & LaTeX Fallback Parser: Translates standard math characters (such as degree symbols, arrows, and Greek letters) into safe LaTeX syntax, falling back gracefully to text rendering if compilation fails.
3. generate_audio.py — Voice Synthesis & Audio Processing
Handles neural voice cloning using Coqui XTTS-v2 and ambient soundscape design.
 * Speaker Latent Caching: Extracts conditioning latents (gpt_cond_latent and speaker_embedding) from the reference voice sample (saem_voice_sample.wav) on first run, providing a 3x speedup across batch rows.
 * Deterministic Reproducibility: Derives a stable 32-bit integer seed from each video_id (SHA-256), ensuring identical voice outputs across re-runs.
 * High-Fidelity Resampling: Resamples audio in-place to canonical 44.1 kHz 16-bit PCM WAV format using scipy.signal.resample_poly with amplitude clipping protection.
 * Integrated Ambient Pad: Generates a low-pass filtered background noise pad matched to target integrated loudness (-34 LUFS) to give narration an atmospheric, professional feel.
 * OOM CPU Failover: Catches GPU CUDA Out-Of-Memory errors and gracefully falls back to CPU rendering without interrupting batch execution.
4. batch_runner.py — Pipeline Orchestration & Stitching
The execution engine that connects audio synthesis, visual rendering, and video assembly.
 * AST Cache Busting: Forces --disable_caching during Manim invocation to prevent stale video frame reuse across identical Python class invocations.
 * FFmpeg Audio-Video Stitching: Combines voice track, background pad, and raw video into a final web-optimized H.264 / AAC MP4 file with trailing audio padding aligned to a 2-second frozen end frame.
 * Environment Isolation: Passes a strictly whitelisted dictionary of environment variables to subprocesses, preventing API key or secret leakage during builds.
 * Resilient Retry Loop: Features automatic exponential backoff retries for transient synthesis or rendering glitches.
 * Filename Sanitization: Uses regex sanitization to ensure safe cross-platform file paths regardless of input string formatting.
5. .github/workflows/render_shorts.yml — Cloud CI/CD Engine
Automates distributed cloud rendering using GitHub Actions.
 * Zero-Dependency Pre-flight Check: Job 1 parses content_batch.csv and validates JSON syntax in under 3 seconds using standard Python libraries before spinning up heavy rendering environments.
 * 4-Worker Matrix Sharding: Job 2 partitions batch rows across a matrix of 4 parallel Ubuntu runners using modular chunk arithmetic (i \pmod N), reducing render time by 75%.
 * PyTorch CPU Optimization: Installs lightweight CPU-only PyTorch wheels (~200 MB) instead of full GPU CUDA packages (~2.5 GB), saving up to 8 minutes per build.
 * Model Weight Caching: Caches XTTS-v2 model checkpoints across runs using GitHub Cache action (actions/cache@v4).
 * Artifact Bundling: Job 3 downloads completed MP4 segments from all parallel runners and aggregates them into a single downloadable ZIP bundle along with execution JSON logs.
6. requirements.txt — Atomic Environment Control
Guarantees reproducible local and cloud build environments.
| Package | Version | Purpose |
|---|---|---|
| manim | 0.18.1 | Core mathematical animation library |
| numpy | 1.26.4 | C-extension array math engine |
| scipy | 1.11.4 | Polyphase audio resampling and filter design |
| torch | 2.2.2 | CPU tensor compute engine for XTTS-v2 |
| TTS | 0.22.0 | Coqui neural voice synthesis framework |
| setuptools | 69.5.1 | Preserves distutils compatibility required by TTS |
🚀 Local Quickstart Guide
Prerequisites
 * Python 3.11 installed
 * FFmpeg installed and added to system PATH
 * System LaTeX distribution installed (texlive-latex-recommended, dvisvgm)
Installation & Execution
 * Clone the Repository:
   git clone https://github.com/saemlabs/physics.git
cd physics

 * Install Dependencies:
   pip install --upgrade "pip<24.1"
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

 * Validate CSV & Setup (Dry Run):
   python batch_runner.py --dry-run

 * Render Full Batch:
   python batch_runner.py

 * Render Specific Video IDs:
   python batch_runner.py --only feynman_01_dipole_torque,feynman_04_lorentz_magic

📊 Visual JSON Schema Example
To render visual scenes dynamically without writing Python code, add JSON arrays to the visual_data_json column in content_batch.csv:
[
  {
    "type": "field",
    "direction": "RIGHT",
    "color": "#3498DB",
    "label": "\\vec{E}"
  },
  {
    "type": "charge",
    "pos": [-1.2, 0.8, 0],
    "color": "#FF4B4B",
    "label": "+q"
  },
  {
    "type": "charge",
    "pos": [1.2, -0.8, 0],
    "color": "#00D2FF",
    "label": "-q"
  },
  {
    "type": "line",
    "start": [-1.2, 0.8, 0],
    "end": [1.2, -0.8, 0],
    "color": "#F1C40F"
  },
  {
    "type": "vector",
    "start": [0, 0, 0],
    "end": [0.4, 1.2, 0],
    "color": "#E74C3C",
    "label": "\\tau",
    "animate": "rotate",
    "rotate_angle": 45
  }
]

