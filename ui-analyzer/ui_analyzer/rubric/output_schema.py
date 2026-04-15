OUTPUT_SCHEMA_XML = """\
Respond with the following XML structure. Do not add prose outside these tags.

<audit_report>
  <confidence level="high|medium|low">
    <!-- Optional reason if medium or low -->
  </confidence>
  <inventory>
    <!-- Step 1: list every interactive element with label, size, color, position -->
  </inventory>
  <structure_observation>
    <!-- Step 2: layout, columns, type scale, color palette -->
  </structure_observation>
  <tier1_findings>
    <finding criterion="1.4.3" element=".nav-link" result="FAIL" estimated="false">
      <observed>contrast ratio 2.8:1</observed>
      <required>4.5:1 for normal text</required>
      <recommendation>Change text color to #374151 (ratio: 7.6:1)</recommendation>
    </finding>
  </tier1_findings>
  <tier2_findings>
    <finding principle="proximity" severity="2" element="Metric cards (top row)">
      <issue>Cards have 4px gap but no separator from filter row above; groups blend.</issue>
      <recommendation>Increase gap between filter bar and metric cards to 24px.</recommendation>
      <nielsen_tag>4</nielsen_tag>
    </finding>
  </tier2_findings>
  <tier3_findings>
    <!-- same structure as tier2_findings, include nielsen_tag -->
  </tier3_findings>
  <tier4_findings>
    <finding pattern="data_ink_ratio" element="Sidebar navigation">
      <issue>6 decorative icons with no text labels at collapsed width; requires memorization.</issue>
      <recommendation>Add persistent text labels or expand sidebar by default.</recommendation>
    </finding>
  </tier4_findings>
</audit_report>"""
