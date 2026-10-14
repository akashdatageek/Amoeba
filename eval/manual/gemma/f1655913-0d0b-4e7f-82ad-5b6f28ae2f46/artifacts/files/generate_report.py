from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_report():
    doc = Document()

    # Set style for the whole document
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(12)

    # Title
    title = doc.add_heading('Executive Report: Top 5 Open-Source Multi-Agent AI Frameworks', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Introduction
    doc.add_heading('Introduction', level=1)
    intro_text = (
        "The landscape of Artificial Intelligence has undergone a paradigm shift, moving from single-prompt "
        "interactions with Large Language Models (LLMs) to the deployment of sophisticated Multi-Agent Systems (MAS). "
        "Multi-agent frameworks allow developers to orchestrate specialized AI agents that can collaborate, debate, "
        "and execute multi-step workflows to solve problems that are far too complex for a single agent to handle reliably. "
        "By decomposing a high-level objective into smaller, role-specific tasks, these frameworks significantly reduce "
        "the likelihood of hallucinations and increase the overall reliability and precision of AI outputs. This executive "
        "report analyzes the five most-starred open-source frameworks on GitHub as of October 2026, evaluating their "
        "market position, community adoption, and architectural contributions to the field of agentic AI."
    )
    doc.add_paragraph(intro_text)

    # Framework Analysis
    doc.add_heading('Framework Analysis', level=1)

    # OpenClaw
    doc.add_heading('OpenClaw', level=2)
    openclaw_text = (
        "OpenClaw is currently the most prominent multi-agent framework by community adoption, boasting 390,572 stars [S25]. "
        "Its massive popularity suggests a strong alignment with developer needs for scalable agent orchestration [S16]. "
        "OpenClaw focuses on providing a robust infrastructure for managing agent lifecycles and communication patterns, "
        "making it a primary choice for enterprises looking to deploy large-scale agentic workflows [S21]. Its dominance "
        "in star count indicates a significant lead in visibility and community-driven extension compared to its peers, "
        "positioning it as the industry standard for high-throughput agent systems."
    )
    doc.add_paragraph(openclaw_text)

    # Dify
    doc.add_heading('Dify', level=2)
    dify_text = (
        "Dify, with 157,267 stars [S25], distinguishes itself by integrating LLMOps (Large Language Model Operations) "
        "directly into the agent orchestration process. Unlike frameworks that focus solely on the logic of agent "
        "interaction, Dify provides a comprehensive platform for prompt engineering, data pipeline management, and "
        "real-time monitoring. This makes it an ideal bridge for teams moving from initial prototypes to production-ready "
        "applications, as it simplifies the operational overhead associated with maintaining multi-agent systems in a "
        "live environment. Dify's approach emphasizes the 'lifecycle' of the agent rather than just the 'logic'."
    )
    doc.add_paragraph(dify_text)

    # Langflow
    doc.add_heading('Langflow', level=2)
    langflow_text = (
        "Langflow follows closely with 155,275 stars [S25]. It is primarily recognized for its intuitive visual interface, "
        "which allows developers to design agentic workflows using a drag-and-drop canvas. By providing a graphical "
        "representation of LangChain components, Langflow lowers the barrier to entry for non-coders and accelerates "
        "the prototyping phase for experienced engineers. This visual-first approach enables rapid iteration of agent "
        "topologies and provides a clearer understanding of data flow between agents, making it highly effective for "
        "rapid experimentation and architectural mapping."
    )
    doc.add_paragraph(langflow_text)

    # AutoGen
    doc.add_heading('AutoGen', level=2)
    autogen_text = (
        "Developed by Microsoft, AutoGen has garnered over 59,059 stars [S26]. It pioneered the concept of 'conversable agents' "
        "that can interact with each other and with humans to solve tasks. AutoGen's strength lies in its extreme flexibility; "
        "it allows for highly customizable conversation patterns, including joint chat and hierarchical orchestration [S13]. "
        "It remains a gold standard for researchers and developers who require fine-grained control over the dialogue "
        "and logic of agent interactions [S26], offering a programmatic depth that is often missing in visual-first platforms."
    )
    doc.add_paragraph(autogen_text)

    # CrewAI
    doc.add_heading('CrewAI', level=2)
    crewai_text = (
        "CrewAI, with 59,059 stars [S25], emphasizes a role-based approach to agent orchestration. It organizes agents into "
        "'crews' where each agent is assigned a specific role, a goal, and a backstory, mimicking a professional human team "
        "structure [S21]. This process-driven methodology makes CrewAI particularly effective for business process "
        "automation and complex content creation workflows, where clear delegation and sequential task execution are "
        "critical for success [S26]. By focusing on the 'persona' of the agent, CrewAI simplifies the definition of "
        "complex organizational behaviors."
    )
    doc.add_paragraph(crewai_text)

    # Chart
    doc.add_heading('Market Visibility Comparison', level=1)
    doc.add_paragraph("The following chart illustrates the distribution of GitHub stars across the top five frameworks, "
                      "highlighting the significant lead held by OpenClaw.")
    doc.add_picture('chart.png', width=Inches(5))
    last_paragraph = doc.paragraphs[-1]
    last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Comparative Summary
    doc.add_heading('Comparative Summary', level=1)
    summary_text = (
        "The data reveals a clear bifurcation in the multi-agent framework market. On one side are the 'Platform' frameworks "
        "like Dify and Langflow, which prioritize visual orchestration and LLMOps to reduce the friction of deployment. "
        "These tools are designed for speed and accessibility. On the other side are the 'Library' frameworks like AutoGen "
        "and CrewAI, which provide programmatic primitives for developers to build custom agentic logic from the ground up. "
        "OpenClaw occupies a unique position, combining massive community traction with a focus on scalable infrastructure. "
        "While AutoGen and CrewAI have similar star counts, they target different philosophies: AutoGen focuses on the "
        "conversation and dialogue flow, while CrewAI focuses on the organizational role and process."
    )
    doc.add_paragraph(summary_text)

    # Conclusion
    doc.add_heading('Conclusion', level=1)
    conclusion_text = (
        "The rapid growth of these frameworks indicates that the industry is moving toward a future where AI is not a "
        "single tool, but a coordinated workforce of specialized agents. As the ecosystem matures, we expect a convergence "
        "where the power of code-first libraries (like AutoGen) is integrated into the accessibility of visual platforms "
        "(like Langflow). For organizations choosing a framework, the decision should be based on the trade-off between "
        "rapid visual prototyping and the need for deep programmatic control. The current trajectory suggests that the "
        "'agentic' layer will become the primary interface for enterprise AI implementation."
    )
    doc.add_paragraph(conclusion_text)

    # References
    doc.add_heading('References', level=1)
    refs = [
        "OpenClaw: [S25] (URL BLOCKED)",
        "Dify: [S25] (URL BLOCKED)",
        "Langflow: [S25] (URL BLOCKED)",
        "AutoGen: github.com/microsoft/autogen [S26]",
        "CrewAI: github.com/crewAIInc/crewAI [S2]"
    ]
    for ref in refs:
        doc.add_paragraph(ref, style='List Bullet')

    doc.save('framework_report.docx')

if __name__ == '__main__':
    create_report()