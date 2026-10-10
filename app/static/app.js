const message = document.querySelector("#message");

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error?.message || "The request could not be completed.");
  }
  return body;
}

function showMessage(text) {
  message.textContent = text;
}

document.querySelector("#student-id").addEventListener("input", (event) => {
  event.currentTarget.value = event.currentTarget.value.toUpperCase();
});

document.querySelector("#question-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = document.querySelector("#question").value;
  try {
    const result = await request("/api/assistant/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    const sources = result.sources.map((source) => `${source.title} — ${source.notice}`);
    document.querySelector("#answer").textContent =
      `${result.answer}${sources.length ? `\n\nSources:\n${sources.join("\n")}` : ""}`;
    showMessage("");
  } catch (error) {
    showMessage(error.message);
  }
});

document.querySelector("#attendance-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const studentId = document.querySelector("#student-id").value;
  const resultContainer = document.querySelector("#attendance-result");
  resultContainer.replaceChildren();
  try {
    const result = await request("/api/attendance", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId }),
    });
    const heading = document.createElement("h3");
    heading.textContent = `Attendance for ${result.student_id}`;
    resultContainer.append(heading);

    if (result.subjects.length === 0) {
      const emptyState = document.createElement("p");
      emptyState.textContent = "No subject attendance is available.";
      resultContainer.append(emptyState);
    } else {
      const table = document.createElement("table");
      const header = table.createTHead().insertRow();
      for (const label of ["Subject", "Attended classes", "Total classes", "Percentage"]) {
        const cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = label;
        header.append(cell);
      }

      const body = table.createTBody();
      for (const subject of result.subjects) {
        const row = body.insertRow();
        for (const value of [
          `${subject.subject} (${subject.subject_code})`,
          subject.attended_classes,
          subject.total_classes,
          `${subject.percentage}%`,
        ]) {
          row.insertCell().textContent = value;
        }
      }
      resultContainer.append(table);
    }
    showMessage("");
  } catch (error) {
    showMessage(error.message);
  }
});

document.querySelector("#policy-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = document.querySelector("#policy-question").value;
  const resultsContainer = document.querySelector("#policy-results");
  resultsContainer.replaceChildren();
  try {
    const result = await request("/api/policy/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    const answer = document.createElement("p");
    answer.textContent = result.answer;
    resultsContainer.append(answer);
    for (const source of result.sources) {
      const citation = document.createElement("small");
      citation.textContent = `${source.source} — ${source.section}`;
      resultsContainer.append(citation);
    }
    showMessage("");
  } catch (error) {
    showMessage(error.message);
  }
});
