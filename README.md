Team Name: Codezilla

Team Members

Member 1:PC Lakshmi Parvathy Thamburatty-ASIET

Member 2: Sandra Madhu-ASIET

Hosted Project Link
Not hosted

Project Description
Data Residue is a secure session-based system that prevents sensitive files from remaining on shared computers. It stores files in a temporary workspace and automatically wipes all data after use, ensuring zero residual traces.

How to run:


First, the operator clicks **“Start Job”**, which creates a secure temporary session. A **QR code** is generated on the right side. The customer scans this QR code using their phone (connected to the same Wi-Fi) and uploads the required document. The uploaded files automatically appear in the **“Files in Current Job”** list inside the application.

The operator then selects a file and clicks **“Open Selected”** to print it normally. After printing is completed, the operator clicks **“End Job (Wipe)”**, which shows a confirmation dialog. Once confirmed, the system securely deletes all files from the session folder, ensuring no sensitive data remains on the computer.

The Problem statement:
We are solving the problem of sensitive files being left behind on shared computers after printing or processing. These leftover documents create serious privacy and security risks. Our system ensures files are used temporarily and automatically wiped, leaving no data residue.

The Solution:
We solve it by creating a secure, session-based workspace where all files are temporarily stored and processed. Once the task is completed, the system automatically wipes all data from the computer. It also follows a zero-trust approach by cleaning any leftover files on startup to prevent accidental data residue.

Technical Details
Technologies/Components Used
For Software:
Python 3 – core application logic

Languages used: Python


Main components: [List main components]
Specifications: [Technical specifications]
Tools required: [List tools needed]
Features
List the key features of your project:
## **Main Components**

* Secure Session Manager
* QR-based File Upload (Flask server)
* File Viewer/Print Module
* Auto Cleanup & Zero-Trust Recovery

---

## **Specifications**

* Platform: Windows
* Language: Python 3
* GUI: Tkinter
* Server: Flask (local)
* Secure wipe: Overwrite + delete
* Works on low-end PCs

---

## **Tools Required**

* Python
* VS Code / any IDE
* pip (Flask, qrcode, Pillow)
* WiFi / hotspot

---

## **Key Features**

* Temporary session workspace
* QR file transfer
* Automatic data wipe
* Startup auto-clean (zero-trust)
* No extra hardware needed

Feature 1: Session-based temporary workspace
Feature 2: QR-based secure file upload

Implementation
For Software:
Installation
bash
pip install flask qrcode pillow
Run
bash
python secureprint_box.py


Circuit Setup
[Explain how to set up the circuit]

Project Documentation
For Software:
Screenshots (Add at least 3)
<img width="950" height="596" alt="image" src="https://github.com/user-attachments/assets/bfb1ad89-3709-448b-a68d-589e6686f601" />
This screenshot shows the **SecurePrint Box (MVP)** application interface.
It displays the main dashboard with options to **Start Job, manage files, and securely wipe data** after use. On the right side, a **QR code** is generated for phone-to-PC file upload, ensuring all files are received inside a temporary secure session. The system is ready to start a new job and prevents uploads until a session is activated.

<img width="925" height="620" alt="image" src="https://github.com/user-attachments/assets/a9a450f2-66a2-4a2b-add0-9d38cbff846e" />
This screenshot shows an **active job session** in SecurePrint Box.
A job has been successfully started, and the uploaded files are now listed under **“Files in Current Job.”** The QR upload system is active, and all documents are securely stored inside the temporary session folder. At this stage, the operator can select a file and click **“Open Selected”** to print it. Once printing is completed, clicking **“End Job (Wipe)”** will automatically delete all files, ensuring no data remains on the system.

<img width="954" height="606" alt="image" src="https://github.com/user-attachments/assets/2ea50b38-211d-4399-ab77-c57284b7bbb3" />
This screenshot shows the **printing and secure cleanup stage** of SecurePrint Box.
A selected file has been opened for printing (“Print as usual”), and the system is now ready to complete the session. When the operator clicks **“End Job (Wipe)”**, a confirmation dialog appears asking to confirm deletion. Once confirmed, all files in the current job session will be securely wiped, ensuring no sensitive data remains on the computer.

