content_batch.csv (Add 100s of rows here)
       │
       ▼
batch_runner.py  ──► generate_audio.py (Generates Voice)
       │
       ▼
render_universal.py (Renders 3b1b animations automatically based on concept_type)
       │
       ▼
FFmpeg (Stitches Audio + Video into output_shorts/)



Physics Shorts Automation Engine


An automated production pipeline built with Manim, Coqui XTTS-v2 Voice Cloning, FFmpeg, and GitHub Actions to generate 9:16 vertical 3Blue1Brown-style physics concept shorts and JEE PYQ solution videos directly from a single CSV configuration file.


📁 Repository Directory Structure
.
├── .github/
│   └── workflows/
│       └── render_shorts.yml    # GitHub Actions workflow for automated cloud rendering
├── content_batch.csv            # Central CSV configuration for all video topics & scripts
├── generate_audio.py            # AI voice synthesis and ambient pad audio processing
├── render_universal.py          # Master 3b1b Manim visual rendering engine
├── batch_runner.py              # Main orchestrator script for batch execution and stitching
├── saem_voice_sample.wav        # 6–10s reference audio sample for XTTS-v2 voice cloning
├── requirements.txt             # Python dependencies and exact framework versions
└── README.md                    # Project documentation



🛠️ Codebase & File Architecture

1. content_batch.csv
The single source of truth for video creation. Adding a new row generates a new video without writing Python code.
 * Supported Headers:
   * video_id: Unique identifier used for output file naming (e.g., dipole_01).
   * concept_type: Selects the animation visual template (DIPOLE_TORQUE, PROJECTILE_MOTION, LORENTZ_FORCE, PYQ).
   * header_title: Main top header text rendered on screen.
   * tagline: Subtitle line rendered directly under the main header.
   * equations_json: JSON string array of LaTeX equations rendered on the math derivation card.
   * audio_script: Plain text script synthesized into speech by the AI voice generator.
   * question_text, option_a...option_d, correct_answer: Optional fields used exclusively when concept_type = PYQ.


2. render_universal.py
The master Manim visual scene engine (UniversalPhysicsScene). It reads row parameters from environment variables injected by batch_runner.py and dynamically executes the visual layout corresponding to CONCEPT_TYPE.
 * Templates Built-in:
   * DIPOLE_TORQUE: Renders 2D uniform electric fields (\vec{E}), dipole moment (\vec{p}), positive and negative point charges, force couple vectors (\vec{F}_+, \vec{F}_-), perpendicular lever arm (d_\perp = 2a\sin\theta), angle reference arc (\theta), and restoring rotational movement.
   * PROJECTILE_MOTION: Renders 2D kinematics coordinate axes, parabolic trajectory plotting, moving particle along the curve, and range/height formulas.
   * LORENTZ_FORCE: Renders magnetic field vectors (\vec{B}), velocity vector (\vec{v}), and circular deflection path geometry.
   * PYQ: Renders formatted multiple-choice exam questions, option grids, equation steps, and animated highlighted answer cards.
   * GENERIC: Default fallback template for general vector algebra and physics derivations.


3. generate_audio.py
Handles speech synthesis and background audio enhancement.
 * Lazy-Loading XTTS-v2: Loads Coqui's multilingual model onto GPU (if available) or CPU.
 * Text Normalization: Enforces trailing punctuation to prevent voice model hallucinations and speech cadence cutoffs.
 * Voice Cloning: Synthesizes natural audio using saem_voice_sample.wav as the reference voice profile.
 * Ambient Pad Generation: Applies a low-pass Butterworth filter (f_c = 400\text{ Hz}) to Gaussian white noise, creating a warm ambient background pad matched to the exact voice track duration.


4. batch_runner.py
The main orchestrator that automates the production workflow step-by-step:
 * Pre-flight Checks: Validates presence of content_batch.csv and saem_voice_sample.wav.
 * Audio Synthesis: Calls synthesize_audio_for_row() to generate _voice.wav and _pad.wav in temp_audio/.
 * Environment Injection: Maps CSV row data into environment variables (HEADER_TITLE, EQUATIONS_JSON, AUDIO_DURATION, etc.) and passes them to Manim.
 * Scene Rendering: Executes manim -qh render_universal.py UniversalPhysicsScene via Python subprocess.
 * FFmpeg Stitching: Merges the voice track, background pad, and rendered video. Applies tpad to freeze the final video frame for 2 seconds and amix to combine audio tracks cleanly without clipping.
 * Error Handling: Catches CalledProcessError exceptions and logs detailed stderr outputs for debugging.


5. .github/workflows/render_shorts.yml
The CI/CD pipeline that automates bulk video generation on GitHub infrastructure:
 * Trigger: Fires automatically on git push to main or manually via workflow_dispatch.
 * Environment Setup: Installs system binaries (ffmpeg, texlive-latex-extra, dvisvgm, libcairo2-dev, libpango1.0-dev).
 * Caching: Caches HuggingFace/Coqui model weights (~2.5GB) to optimize build times.
 * Artifact Upload: Compiles all rendered MP4 shorts into output_shorts/ and uploads them as a downloadable artifact zip file.


⚡ Local Setup & Execution
Prerequisites

Ensure your local machine has FFmpeg and a working LaTeX distribution (texlive or miktex) installed.
Installation
 * Clone the repository:
   git clone https://github.com/saemlabs/physics.git
cd physics

 * Install Python dependencies:
   pip install --upgrade "pip<24.1"
pip install -r requirements.txt






 * Provide Reference Voice Sample:
   Ensure a clear 6–10 second WAV file named saem_voice_sample.wav is placed in the root folder.
Running Batch Production
Execute the batch runner to generate all videos listed in content_batch.csv:
python batch_runner.py

Final videos will be saved in the output_shorts/ directory with the _final.mp4 suffix.
