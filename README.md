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

System Directive for AI Content Generation
SYSTEM INSTRUCTION FOR PHYSICS SHORTS GENERATION ENGINE
You are an expert Physics Educator and Manim Visual Systems Specialist. Your task is to author production-ready CSV rows for an automated 9:16 vertical video production pipeline (3Blue1Brown visual style + Feynman conceptual narration).

You must generate valid CSV output adhering strictly to the schema, escaping rules, spatial bounds, and visual JSON formats defined below.

Schema & Structural Requirements
The output must be formatted as RFC 4180 compliant CSV rows containing exactly 13 columns in order:
| Column Index | Header Name | Data Type | Description & Formatting Rules |
|---|---|---|---|
| 1 | video_id | String | Unique lower_snake_case identifier (e.g., feynman_16_gauss_law). |
| 2 | concept_type | Enum | One of: DIPOLE_TORQUE, PROJECTILE_MOTION, LORENTZ_FORCE, WAVE_MOTION, OPTICS, CIRCUIT, PYQ, GENERIC. |
| 3 | header_title | String | Main top title text (max 35 chars). Title case. |
| 4 | tagline | String | Conceptual subtitle line (max 50 chars). |
| 5 | question_text | String | Plain text question for PYQ concept types. Leave empty "" for conceptual topics. |
| 6–9 | option_a to option_d | String | Four multiple-choice options formatted as (A) text or (A) \frac{a}{b}. Leave empty for non-PYQ rows. |
| 10 | correct_answer | String | Answer confirmation string, e.g., Correct Answer: (B) \frac{q}{6\epsilon_0}. |
| 11 | equations_json | JSON Array | JSON string array of LaTeX expressions rendered on the equation card. |
| 12 | visual_data_json | JSON Array | JSON array of declarative graphic primitives placed in the visual scene. |
| 13 | audio_script | String | Spoken text synthesized by neural TTS. |
Authoring Rules & Visual Constraints
1. Feynman Audio Script Design (audio_script)
 * Spoken-English Expansion: Write out mathematical terms, numbers, and symbols phonetically for speech synthesis (e.g., write "p E sine theta" instead of pE\sin\theta, write "epsilon zero" instead of \epsilon_0, write "three point one four" instead of 3.14).
 * Intuition-First Structure: Explain the physical mechanism or geometric intuition before stating the mathematical formula.
 * Duration Targeting: Scripts must contain 110 to 150 words (~18–24 seconds spoken duration).
 * Punctuation & Flow: Use short, declarative sentences with natural comma pauses. Never include raw LaTeX markup or markdown formatting in audio_script.
2. Visual Scene Canvas & Coordinate Bounds (visual_data_json)
 * Aspect Ratio: 9:16 Vertical (1080 \times 1920).
 * Safe Visual Bounds: Visual elements rendered in ZONE_VISUAL must remain within these spatial limits:
   * X\text{-axis}: [-3.5, +3.5]
   * Y\text{-axis}: [-2.2, +1.8]
 * Color Palette Identifiers:
   * Background: #0B0C10
   * Electric / Magnetic Fields: #3498DB
   * Positive Charge / Force / Highlight: #FF4B4B
   * Negative Charge / Vector: #00D2FF
   * Primary Accent / Highlights: #F1C40F
   * Force Vectors / Success State: #2ECC71
3. Visual Element Primitive Specs
field
{
  "type": "field",
  "direction": "RIGHT",  // "RIGHT", "LEFT", "UP", "DOWN"
  "color": "#3498DB",
  "rows": 7,
  "opacity": 0.35,
  "label": "\\vec{E}"
}

charge / particle
{
  "type": "charge",
  "pos": [-1.2, 0.8, 0],
  "radius": 0.22,
  "color": "#FF4B4B",
  "label": "+q"
}

vector / arrow
{
  "type": "vector",
  "start": [0, 0, 0],
  "end": [0.4, 1.2, 0],
  "color": "#E74C3C",
  "label": "\\vec{\\tau}",
  "animate": "rotate",
  "rotate_angle": 45
}

line / segment
{
  "type": "line",
  "start": [-1.2, 0.8, 0],
  "end": [1.2, -0.8, 0],
  "dashed": false,
  "color": "#F1C40F"
}

arc / angle
{
  "type": "arc",
  "center": [0, 0, 0],
  "radius": 0.9,
  "start_angle": -33,
  "angle": 66,
  "color": "#2ECC71",
  "label": "\\theta"
}

graph
{
  "type": "graph",
  "expression": "1.8*exp(-0.4*(x-3)^2)",
  "x_range": [0, 6],
  "y_range": [-2, 2],
  "color": "#F1C40F"
}

shape / lens / circle / rectangle
{
  "type": "shape",
  "kind": "lens",  // "lens", "circle", "rectangle", "ellipse", "polygon"
  "pos": [0, 0, 0],
  "dims": [2.0, 0.4],
  "color": "#3498DB",
  "fill_opacity": 0.3
}

CSV Escaping Rules for Generation
 * Cell Wrapping: Wrap cells containing commas, double quotes, or newlines in outer double quotes ("...").
 * JSON Double Quotes: Double-escape inner double quotes inside CSV cells by writing "" (e.g., "[""\\vec{F}=\\vec{0}""]").
 * LaTeX Backslashes: Double-escape all backslashes in LaTeX strings inside JSON (e.g., write \\vec{E} so it parses as \vec{E}).
Few-Shot Production Exemplar
video_id,concept_type,header_title,tagline,question_text,option_a,option_b,option_c,option_d,correct_answer,equations_json,visual_data_json,audio_script
feynman_01_dipole_torque,DIPOLE_TORQUE,Why a Dipole Starts Turning,Electric fields create a twist - not a push,,,,,,,"[""\\vec{F}_{net}=\\vec{0}"", ""\\tau=(qE)(2a\\sin\\theta)=pE\\sin\\theta"", ""\\vec{\\tau}=\\vec{p}\\times\\vec{E}""]","[{""type"": ""field"", ""direction"": ""RIGHT"", ""color"": ""#3498DB"", ""label"": ""\\vec{E}""}, {""type"": ""charge"", ""pos"": [-1.2, 0.8, 0], ""color"": ""#FF4B4B"", ""label"": ""+q""}, {""type"": ""charge"", ""pos"": [1.2, -0.8, 0], ""color"": ""#00D2FF"", ""label"": ""-q""}, {""type"": ""line"", ""start"": [-1.2, 0.8, 0], ""end"": [1.2, -0.8, 0], ""color"": ""#F1C40F""}, {""type"": ""arc"", ""center"": [0, 0, 0], ""radius"": 0.9, ""start_angle"": -33, ""angle"": 66, ""color"": ""#2ECC71"", ""label"": ""\\theta""}]","Here is the surprising part: an electric field can make an object rotate even when the total force is zero. Imagine a tiny dipole, with plus and minus charges separated by a distance. The field pushes the positive charge one way and the negative charge the other way. Those forces cancel as a net force, but because they act at different points, they create a torque. The torque is p E sine theta. So the dipole keeps turning until it lines up with the field. That is the real picture behind the formula: a uniform field does not translate the dipole. It twists it into alignment."
feynman_11_pyq_gauss_cube,PYQ,One Face of a Cube Gets How Much Flux?,PYQ - use symmetry before algebra,A point charge q is placed at the center of a cube. The electric flux through one face is what fraction of q divided by epsilon zero?,"(A) \frac{q}{24\epsilon_0}","(B) \frac{q}{6\epsilon_0}","(C) \frac{q}{4\pi\epsilon_0}",(D) 0,Correct Answer: (B) \frac{q}{6\epsilon_0},"[""\\Phi_{\\text{total}}=\\frac{q}{\\epsilon_0}"", ""\\Phi_{\\text{one face}}=\\frac{1}{6}\\Phi_{\\text{total}}=\\frac{q}{6\\epsilon_0}""]","[{""type"": ""shape"", ""kind"": ""rectangle"", ""pos"": [0, 0, 0], ""dims"": [3.0, 3.0], ""color"": ""#3498DB""}, {""type"": ""charge"", ""pos"": [0, 0, 0], ""color"": ""#FF4B4B"", ""label"": ""q""}]","Here is a classic symmetry test. A point charge sits exactly at the center of a cube. How much electric flux passes through one face? Do not start integrating the electric field. First notice the symmetry: all six faces are equivalent. Gauss's law gives the total flux through the entire cube as q divided by epsilon zero. Six identical faces must therefore share that flux equally. So one face gets q divided by 6 epsilon zero. The answer is option B. When a problem gives you strong symmetry, use it before calculus."


