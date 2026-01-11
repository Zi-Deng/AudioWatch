"""Watch Rules management page for AudioWatch dashboard."""

from __future__ import annotations

import streamlit as st

from audiowatch.dashboard.db import (
    create_watch_rule,
    delete_watch_rule,
    get_watch_rules,
    update_watch_rule,
)


def render():
    """Render the watch rules management page."""
    st.title("Watch Rules")
    st.markdown("Create and manage rules for matching listings and sending notifications.")

    # Initialize session state for edit mode
    if "edit_rule_id" not in st.session_state:
        st.session_state.edit_rule_id = None

    # Two columns: rules list and form
    col_list, col_form = st.columns([2, 1])

    with col_list:
        st.subheader("Your Rules")
        rules_df = get_watch_rules()

        if rules_df.empty:
            st.info("No watch rules created yet. Create one using the form on the right.")
        else:
            # Display rules as cards
            for _, rule in rules_df.iterrows():
                _render_rule_card(rule)

    with col_form:
        if st.session_state.edit_rule_id:
            _render_edit_form(st.session_state.edit_rule_id, rules_df)
        else:
            _render_create_form()

    # Expression syntax help
    st.divider()
    with st.expander("Expression Syntax Help"):
        st.markdown("""
        ### Boolean Operators
        - `AND` - Both conditions must match
        - `OR` - Either condition matches
        - `NOT` - Negates the condition
        - Use parentheses for grouping: `(A OR B) AND C`

        ### Comparison Operators
        | Operator | Example | Description |
        |----------|---------|-------------|
        | `=` | `category = "headphones"` | Exact match |
        | `!=` | `seller != "baduser"` | Not equal |
        | `<` | `price < 1000` | Less than |
        | `>` | `price > 500` | Greater than |
        | `<=` | `price <= 2000` | Less than or equal |
        | `>=` | `seller_reputation >= 10` | Greater than or equal |

        ### String Operators
        | Operator | Example | Description |
        |----------|---------|-------------|
        | `contains` | `title contains "HD800"` | Substring match |
        | `startswith` | `title startswith "Sennheiser"` | Starts with |
        | `endswith` | `title endswith "mint"` | Ends with |
        | `matches` | `title matches "64\\s*Audio"` | Regex pattern |
        | `fuzzy_contains` | `title fuzzy_contains "ThieAudio"` | Fuzzy match |

        ### Available Fields
        `title`, `price`, `currency`, `category`, `condition`, `listing_type`,
        `ships_to`, `status`, `seller`, `seller_reputation`

        ### Examples
        ```
        title contains "HD800" AND price < 1000
        (title contains "Focal" OR title contains "Sennheiser") AND price < 2000
        title fuzzy_contains "ThieAudio Monarch" AND condition = "Excellent"
        title matches "64\\s*[Aa]udio" AND seller_reputation >= 5
        ```
        """)


def _render_rule_card(rule):
    """Render a single rule as a card."""
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])

        with col1:
            # Status indicator
            status_icon = "✅" if rule["Enabled"] else "⏸️"
            st.markdown(f"### {status_icon} {rule['Name']}")
            st.code(rule["Expression"], language=None)
            st.caption(f"Notify via: {rule['Notify Via']} | Created: {rule['Created'].strftime('%Y-%m-%d')}")

        with col2:
            st.write("")  # Spacing
            st.write("")

            # Action buttons
            col_edit, col_toggle, col_delete = st.columns(3)

            with col_edit:
                if st.button("✏️", key=f"edit_{rule['ID']}", help="Edit rule"):
                    st.session_state.edit_rule_id = rule["ID"]
                    st.rerun()

            with col_toggle:
                toggle_label = "⏸️" if rule["Enabled"] else "▶️"
                toggle_help = "Disable" if rule["Enabled"] else "Enable"
                if st.button(toggle_label, key=f"toggle_{rule['ID']}", help=toggle_help):
                    update_watch_rule(rule["ID"], enabled=not rule["Enabled"])
                    st.rerun()

            with col_delete:
                if st.button("🗑️", key=f"delete_{rule['ID']}", help="Delete rule"):
                    delete_watch_rule(rule["ID"])
                    st.toast(f"Deleted rule: {rule['Name']}")
                    st.rerun()


def _render_create_form():
    """Render the create rule form."""
    st.subheader("Create New Rule")

    with st.form("create_rule_form"):
        name = st.text_input(
            "Rule Name",
            placeholder="e.g., Budget IEMs",
            help="A descriptive name for this rule",
        )

        expression = st.text_area(
            "Expression",
            placeholder='title contains "HD800" AND price < 1000',
            help="Boolean expression to match listings",
            height=100,
        )

        notify_via = st.multiselect(
            "Notify Via",
            options=["discord", "email"],
            default=["discord"],
            help="Channels to send notifications to",
        )

        enabled = st.checkbox("Enabled", value=True)

        submitted = st.form_submit_button("Create Rule", type="primary", use_container_width=True)

        if submitted:
            if not name:
                st.error("Please enter a rule name.")
            elif not expression:
                st.error("Please enter an expression.")
            elif not notify_via:
                st.error("Please select at least one notification channel.")
            else:
                try:
                    rule_id = create_watch_rule(
                        name=name,
                        expression=expression,
                        notify_via=notify_via,
                        enabled=enabled,
                    )
                    st.success(f"Created rule: {name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create rule: {e}")


def _render_edit_form(rule_id: int, rules_df):
    """Render the edit rule form."""
    st.subheader("Edit Rule")

    # Get the rule data
    rule = rules_df[rules_df["ID"] == rule_id].iloc[0]

    with st.form("edit_rule_form"):
        name = st.text_input("Rule Name", value=rule["Name"])

        expression = st.text_area(
            "Expression",
            value=rule["Expression"],
            height=100,
        )

        current_channels = rule["Notify Via"].split(",")
        notify_via = st.multiselect(
            "Notify Via",
            options=["discord", "email"],
            default=current_channels,
        )

        enabled = st.checkbox("Enabled", value=rule["Enabled"])

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
        with col2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if submitted:
            if not name or not expression or not notify_via:
                st.error("Please fill in all fields.")
            else:
                try:
                    update_watch_rule(
                        rule_id=rule_id,
                        name=name,
                        expression=expression,
                        notify_via=notify_via,
                        enabled=enabled,
                    )
                    st.success(f"Updated rule: {name}")
                    st.session_state.edit_rule_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update rule: {e}")

        if cancelled:
            st.session_state.edit_rule_id = None
            st.rerun()
