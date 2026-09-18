function sendResearchInternshipEmails() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("UTC-4"); // IMPORTANT: Replace with your sheet name (e.g., "Professors")
  if (!sheet) {
    console.error("Error: Sheet 'UTC-4' not found. Please update the sheet name in the script.");
    return;
  }
  const dataRange = sheet.getDataRange();
  const values = dataRange.getValues();

  // --- Configuration ---
  const RESUME_FILE_ID = "";
  
  // Update these with your personal information
  const YOUR_NAME = "Pranay Saini";
  const YOUR_DEPARTMENT = "Biomedical Engineering";
  const YOUR_UNIVERSITY = "IIT (BHU), Varanasi";
  const YOUR_EMAIL = "";
  const YOUR_PHONE = "";

  // --- Column Header Definitions (match your sheet headers exactly) ---
  const HEADER_ROW = 0;
  const PROFESSOR_NAME_COL = values[HEADER_ROW].indexOf("Faculty Name");
  const PROFESSOR_EMAIL_COL = values[HEADER_ROW].indexOf("Email");
  const AREA_OF_INTEREST_COL = values[HEADER_ROW].indexOf("Research Focus");

  if (PROFESSOR_NAME_COL === -1 || PROFESSOR_EMAIL_COL === -1 || AREA_OF_INTEREST_COL === -1) {
    console.error("Error: One or more required header columns (Faculty Name, Email, Research Focus) are missing. Please check your sheet headers.");
    return;
  }

  let resumeFile;
  try {
    resumeFile = DriveApp.getFileById(RESUME_FILE_ID);
  } catch (e) {
    console.error(`Error: Could not find Resume PDF with ID: ${RESUME_FILE_ID}. Please ensure the ID is correct and the file exists. Error: ${e.message}`);
    return;
  }

  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const professorName = row[PROFESSOR_NAME_COL];
    const professorEmail = row[PROFESSOR_EMAIL_COL];
    const areaOfInterest = row[AREA_OF_INTEREST_COL];

    if (!professorEmail) {
      console.log(`Skipping row ${i + 1}: Missing professor email. Professor Name: ${professorName || 'N/A'}.`);
      continue;
    }
    
    // Check if the row's background is the default white color
    const rowRange = sheet.getRange(i + 1, 1, 1, sheet.getLastColumn());
    if (rowRange.getBackground() === '#ffffff') {
      
      // Final content for the email body.
      const subject = `Research Internship Application - Summer 2026`;
      
      const body = `Dear ${professorName},<p>` +
                   `My name is ${YOUR_NAME}, a third-year ${YOUR_DEPARTMENT} undergraduate at ${YOUR_UNIVERSITY}, with a strong interest in bio-instrumentation, wearable sensor systems, and machine learning for biomedical applications.<p>` +
                   `I have worked on projects including a vision-based motion intent detection system using a CNN–LSTM pipeline for upper limb tasks, and an orientation estimation system on the Seeed Studio XIAO IMU with calibration and Madgwick filtering. I also presented work on sMRI-based machine learning for ASD diagnosis at IEEE EMBC 2025.<p>` +
                   `I have a strong academic record (CGPA: 8.78/10), Department Rank 2, and am eager to contribute to research projects.<p>` +
                   `I am seeking a Summer 2026 research internship and would be grateful for the opportunity to contribute to your lab’s work in ${areaOfInterest}. My CV is attached for your consideration.<p>` +
                   `Thank you for your time and consideration.<p>` +
                   `Sincerely,<br>` +
                   `${YOUR_NAME}<br>` +
                   `${YOUR_UNIVERSITY}<br>` +
                   `${YOUR_PHONE}`;

      try {
        GmailApp.sendEmail(professorEmail, subject, "", {
          htmlBody: body,
          attachments: [resumeFile.getAs(MimeType.PDF)]
        });

        // Set the background color to a light green to indicate the email has been sent
        rowRange.setBackground("#d9ead3");
        console.log(`Research internship email sent to Prof. ${professorName} (${professorEmail}).`);

      } catch (e) {
        console.error(`Error sending email to Prof. ${professorName} (${professorEmail}): ${e.message}`);
      }
    } else {
      console.log(`Skipping row ${i + 1}: Email already sent to ${professorName}.`);
    }

    Utilities.sleep(1000); 
  }
  console.log("Research internship email sending process complete. Check 'Executions' tab for details and your Gmail 'Sent' folder.");
}
