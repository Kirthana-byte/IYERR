IYER

Project Overview

IYER is a vision-based autonomous robot fetching system designed to explore intelligent robotic interaction with a simulated environment. The project combines physics-based simulation, camera-based visual feedback, and AI-assisted decision-making to enable a robot to identify objects, navigate its surroundings, pick up target objects, and deliver them to a designated location.

Developed using Python, the system uses PyBullet to simulate the robot and its environment. Camera input provides visual information about the surroundings, which is used for environmental understanding and decision-making. Claude API integration enables AI-based visual reasoning to help determine appropriate robot actions.

The robot operates through a feedback-driven workflow. It observes the environment, processes visual information, determines the next action, and executes the corresponding movement. The system includes movement, turning, object pickup, and object-drop operations. A state-machine-based control mechanism helps coordinate the different stages of task execution.

Flask is used for the application interface, while logging mechanisms record execution details in JSONL format and capture PNG frames for debugging and analysis. The project also incorporates collision recovery logic to improve the robot's ability to handle navigation difficulties.

Automated testing is performed using pytest to evaluate individual system components and functionalities. The project is currently an evolving prototype, with ongoing work focused on improving object pickup reliability, navigation efficiency, visual reasoning, and complete autonomous task execution.

The long-term vision of IYER is to develop an intelligent robotic system capable of observing, understanding, and interacting with its environment with minimal human intervention.

## Objectives

- To develop a simulated autonomous robot capable of navigating an environment and performing object-fetching tasks.
- To integrate camera-based visual feedback and AI-assisted reasoning for environment understanding and decision-making.
- To implement reliable robot movement, object pickup, delivery, and recovery mechanisms.

## Technologies Used

- Python 3.11
- PyBullet – Physics-based robot simulation
- Flask – Application/backend interface
- Claude API – AI-based visual reasoning
- pytest – Automated testing
- JSONL – Execution logging
- PNG – Visual frame capture

## Project Structure

- **src/** – Contains the main application and robot control logic.
- **tests/** – Contains automated test cases using pytest.
- **assets/** – Stores project-related visual assets and resources.
- **logs/** – Stores execution logs and debugging information.
- **frames/** – Contains captured PNG frames from the simulation.
- **README.md** – Provides project documentation and instructions.
- **requirements.txt** – Lists the Python dependencies required to run the project.

*Note: Folder names should be adjusted to match the actual repository structure.*

## Installation and Execution

1. Clone the repository:

   ```bash
   git clone <repository-url>
   ```

2. Navigate to the project directory:

   ```bash
   cd IYER
   ```

3. Create a virtual environment:

   ```bash
   python -m venv venv
   ```

4. Activate the virtual environment:

   **Windows:**
   ```bash
   venv\Scripts\activate
   ```

   **Linux/macOS:**
   ```bash
   source venv/bin/activate
   ```

5. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

6. Configure the required API credentials as environment variables before running the application.

7. Execute the project's main entry-point script:

   ```bash
   python <main-file>.py
   ```

   *Replace `<main-file>.py` with the actual entry-point filename.*

## Contributors

- Mrinal.M
- Samruddh.B.Patil
- Kirthana.JL
- Abhitha.Rohith
