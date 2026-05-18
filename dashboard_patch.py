# USUŃ TEN BLOK:
# --------------------------------
with cols[-1]:
    st.markdown('<div class="ai-status-col">', unsafe_allow_html=True)
    if st.button(status_label, key=f"btn_{key}", use_container_width=True):
        st.session_state[key] = not st.session_state[key]
    st.markdown('</div>', unsafe_allow_html=True)

# I WSTAW TO:
# --------------------------------
status_html = f"""
<div class="ai-status"
onclick="
const details=document.getElementById('details_{key}');
if(details.style.display==='none'){details.style.display='block';}
else{details.style.display='none';}
">
    {status_label}
</div>
"""

row_html = row_html.replace(
    '<div></div></div></div>',
    f'<div>{status_html}</div></div></div>'
)

st.markdown(row_html, unsafe_allow_html=True)
