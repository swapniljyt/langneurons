"""
core/tools/intelligence/sei_tools.py
──────────────────────────────────────
Shared Engineering Intelligence (SEI) population tools.

Reserved exclusively for the root_neuron / Project Coordinator.
These tools populate a global knowledge store that every child agent
reads as their "zero-th context" before starting any work.

Moved from: core/tools/intelligence_tools.py
"""

from __future__ import annotations
import json
from langchain_core.tools import tool


def _get_sei(session_id: str = "default"):
    try:
        from ...memory.shared_intelligence import SharedIntelligenceStore
        return SharedIntelligenceStore(session_id=session_id)
    except ImportError:
        raise RuntimeError(
            "SharedIntelligenceStore has been removed. "
            "SEI tools are only used during the unfreeze phase and are not available in freeze mode."
        )



def create_sei_tools(session_id: str) -> list:
    """
    Create the full set of SEI population tools bound to a specific session.
    These are injected into the root_neuron's toolset only.

    Returns a list of LangChain tool objects.
    """

    @tool
    def set_product_vision(
        name: str,
        purpose: str,
        target_users: str,
        core_features: list,
        non_goals: list = None,
    ) -> str:
        """
        Populate the product vision in the Shared Engineering Intelligence.
        Call this FIRST, before any other SEI tool.

        Args:
            name:          Short name of the product/project
            purpose:       One or two sentences on why this product exists
            target_users:  Who will use this product
            core_features: List of primary features or deliverables
            non_goals:     Explicit list of things we are NOT building
        """
        sei = _get_sei(session_id)
        sei.update_section("product_vision", {
            "name": name, "purpose": purpose,
            "target_users": target_users,
            "core_features": core_features or [],
            "non_goals": non_goals or [],
        })
        sei.append_change(by_agent="root_neuron", section="product_vision",
                          change=f"Set product vision: {name}", impacts=["all"])
        return f"✅ Product vision set: '{name}'"

    @tool
    def set_architecture_map(modules: dict) -> str:
        """
        Define the full module architecture for the project.

        Args:
            modules: Dict of module_name → module_definition.
                     Each definition supports:
                       role        — what this module does
                       namespace   — directory or domain it owns (e.g., 'frontend/')
                       owned_by    — agent common_name responsible for this module
                       depends_on  — list of interface names this module consumes
                       exposes     — list of interface names this module produces
        """
        sei = _get_sei(session_id)
        sei.update_section("architecture_map", {"modules": modules})
        sei.append_change(by_agent="root_neuron", section="architecture_map",
                          change=f"Defined {len(modules)} modules: {', '.join(modules.keys())}",
                          impacts=["all"])
        return f"✅ Architecture map set with {len(modules)} modules: {', '.join(modules.keys())}"

    @tool
    def set_tech_stack(decisions: dict) -> str:
        """
        Register the official technology and tooling decisions for the project.

        Args:
            decisions: Dict of domain → tool choices.
                       Keys can be any domain name. Values are dicts of
                       role → chosen_tool pairs, or plain strings.
        """
        sei = _get_sei(session_id)
        sei.update_section("tech_stack", decisions)
        sei.append_change(by_agent="root_neuron", section="tech_stack",
                          change=f"Set tech stack for: {', '.join(decisions.keys())}",
                          impacts=["all"])
        return f"✅ Tech stack set for domains: {', '.join(decisions.keys())}"

    @tool
    def set_standards(
        naming: dict = None, api: dict = None,
        git: dict = None, other: dict = None,
    ) -> str:
        """
        Set the coding and collaboration standards for the entire team.

        Args:
            naming: File, function, class, and variable naming conventions
            api:    API design rules (versioning, error codes, auth patterns)
            git:    Branch naming, commit message format
            other:  Any other standards (documentation, testing, etc.)
        """
        sei = _get_sei(session_id)
        combined = {}
        if naming: combined["naming"] = naming
        if api:    combined["api"]    = api
        if git:    combined["git"]    = git
        if other:  combined.update(other)
        sei.update_section("standards", combined)
        sei.append_change(by_agent="root_neuron", section="standards",
                          change=f"Set standards for: {', '.join(combined.keys())}",
                          impacts=["all"])
        return f"✅ Standards set for: {', '.join(combined.keys())}"

    @tool
    def publish_interface(
        interface_name: str,
        produced_by: str,
        consuming_modules: list,
        spec: dict,
    ) -> str:
        """
        Register a formal cross-domain interface in the Shared Engineering Intelligence.

        Args:
            interface_name:    Unique name, versioned if needed (e.g., 'api_v1')
            produced_by:       Your module name (e.g., 'backend')
            consuming_modules: List of module names that depend on this interface
            spec:              Free-form dict describing the interface
        """
        sei = _get_sei(session_id)
        sei.register_interface(
            interface_name=interface_name,
            produced_by=produced_by,
            consuming_modules=consuming_modules,
            spec=spec,
        )
        consumer_str = ", ".join(consuming_modules)
        return (
            f"✅ Interface '{interface_name}' registered.\n"
            f"   Produced by: {produced_by}\n"
            f"   Consumed by: {consumer_str}\n"
            f"   Consumers will receive full spec in their context before they act."
        )

    return [
        set_product_vision,
        set_architecture_map,
        set_tech_stack,
        set_standards,
        publish_interface,
    ]
