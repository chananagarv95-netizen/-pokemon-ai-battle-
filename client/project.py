!pip install reportlab
!pip install pandas numpy matplotlib scikit-learn gradio
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import gradio as gr
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# -----------------------------
# DATASET
# -----------------------------
np.random.seed(42)

data = {
    "mst1": np.random.randint(5, 20, 100),
    "mst2": np.random.randint(5, 20, 100),
    "assignment": np.random.randint(5, 12, 100),
    "quiz": np.random.randint(2, 6, 100),
    "case": np.random.randint(5, 10, 100),
    "attendance": np.random.randint(1, 2, 100),
    "est": np.random.randint(20, 50, 100)
}

df = pd.DataFrame(data)

df["final_score"] = (
    df["attendance"] +
    df["mst1"] +
    df["mst2"] +
    df["assignment"] +
    df["quiz"] +
    df["case"] +
    df["est"]
)

# -----------------------------
# MODEL
# -----------------------------
X = df.drop("final_score", axis=1)
y = df["final_score"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

model = RandomForestRegressor()
model.fit(X_train, y_train)

# -----------------------------
# GRADING
# -----------------------------
def assign_grade(p):
    if p >= 90: return "O"
    elif p >= 80: return "A+"
    elif p >= 70: return "A"
    elif p >= 60: return "B+"
    elif p >= 50: return "B"
    else: return "C"

# -----------------------------
# MAIN FUNCTION
# -----------------------------
def student_analysis(name, att, mst1, mst2, assignment, quiz, case, target):

    current_internal = att + mst1 + mst2 + assignment + quiz + case

    predicted = model.predict([[mst1, mst2, assignment, quiz, case, att, 30]])[0]

    # ✅ REAL PERCENTILE
    percentile = (df["final_score"] < predicted).mean() * 100
    grade = assign_grade(percentile)

    # ✅ Required EST
    required_est = target - current_internal
    required_est = max(0, min(50, required_est))

    avg_score = df["final_score"].mean()

    # -----------------------------
    # TIPS
    # -----------------------------
    tips = []
    weak = []

    if mst1 < 10:
        tips.append("Revise MST-1 topics regularly")
        weak.append("MST-1")

    if mst2 < 10:
        tips.append("Focus on MST-2 concepts")
        weak.append("MST-2")

    if assignment < 8:
        tips.append("Submit higher quality assignments")
        weak.append("Assignments")

    if quiz < 4:
        tips.append("Practice quizzes weekly")
        weak.append("Quiz")

    if case < 6:
        tips.append("Improve case study understanding")
        weak.append("Case Study")

    if not tips:
        tips.append("Excellent performance, maintain consistency")

    # -----------------------------
    # EXPLANATION
    # -----------------------------
    explanation = f"""
This prediction is based on your internal performance and learned data patterns.

• Internal Score: {round(current_internal,2)} / 50
• Predicted Final Score: {round(predicted,2)} / 100

Key Insight:
Students with strong MST and assignment performance tend to score higher.

Weak Areas:
{', '.join(weak) if weak else 'None'}

Improving these areas can significantly boost your final result.
"""

    required_est_text = f"""
To achieve a target score of {target}/100:

You need approximately {round(required_est,2)} marks out of 50
in the End Semester Exam (EST).

This assumes your internal score remains {round(current_internal,2)}.
"""

    # -----------------------------
    # GRAPHS
    # -----------------------------
    plt.figure()
    plt.bar(["Your Score", "Class Avg"], [predicted, avg_score])
    plt.title("Performance Comparison")
    plt.savefig("/tmp/performance.png")
    plt.close()

    plt.figure()
    plt.bar(["Internal Score", "Required EST"], [current_internal, required_est])
    plt.title("Marks Requirement Analysis")
    plt.savefig("/tmp/marks.png")
    plt.close()

    graph_explanation = """
Graph 1: Compares your predicted performance with class average.

Graph 2: Shows your current internal marks vs required EST marks to reach target.
"""

    # -----------------------------
    # PDF REPORT
    # -----------------------------
    file_path = f"/tmp/{name}_report.pdf"
    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("ACADEMIC PERFORMANCE REPORT", styles['Title']))
    content.append(Spacer(1, 12))

    content.append(Paragraph(f"Student Name: {name}", styles['Heading2']))
    content.append(Spacer(1, 10))

    content.append(Paragraph("Performance Summary:", styles['Heading2']))
    content.append(Paragraph(f"Predicted Score: {round(predicted,2)} / 100", styles['Normal']))
    content.append(Paragraph(f"Grade: {grade}", styles['Normal']))
    content.append(Paragraph(f"Percentile: {round(percentile,2)}%", styles['Normal']))

    content.append(Spacer(1, 10))
    content.append(Paragraph("Detailed Analysis:", styles['Heading2']))
    content.append(Paragraph(explanation, styles['Normal']))

    content.append(Spacer(1, 10))
    content.append(Paragraph("Target Planning:", styles['Heading2']))
    content.append(Paragraph(required_est_text, styles['Normal']))

    content.append(Spacer(1, 10))
    content.append(Paragraph("Recommendations:", styles['Heading2']))
    for tip in tips:
        content.append(Paragraph(f"• {tip}", styles['Normal']))

    content.append(Spacer(1, 10))
    content.append(Paragraph("Visual Insights:", styles['Heading2']))
    content.append(Paragraph(graph_explanation, styles['Normal']))

    content.append(Image("/tmp/performance.png", width=400, height=200))
    content.append(Image("/tmp/marks.png", width=400, height=200))

    doc.build(content)

    return file_path, "/tmp/performance.png", "/tmp/marks.png"

# -----------------------------
# UI
# -----------------------------
interface = gr.Interface(
    fn=student_analysis,
    inputs=[
        gr.Textbox(label="Student Name"),
        gr.Number(label="Attendance (out of 2)"),
        gr.Number(label="MST-1 (out of 20)"),
        gr.Number(label="MST-2 (out of 20)"),
        gr.Number(label="Assignment (out of 12)"),
        gr.Number(label="Quiz (out of 6)"),
        gr.Number(label="Case Study (out of 10)"),
        gr.Number(label="Target Marks (out of 100)")
    ],
    outputs=[
        gr.File(label="Download Report"),
        gr.Image(label="Performance Graph"),
        gr.Image(label="Marks Analysis Graph")
    ],
    title="🎓 CU Student Performance Intelligence System",
    description="AI-based academic advisor with prediction, ranking, graphs, and professional report"
)

interface.launch()