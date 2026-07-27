"""REP التشغيلية — العهدة والمستندات والحركة، كداتا يتقرا منها.

The REP single-file PWA carried its data inside its own <script> tag, which
meant the only consumer that data could ever have was that one page. Extracted
into `data/rep/rep.json` and served from here, the same records become a
connector: the workspace, the hub, the tour and management reports all read
them the way they read Nama — and the page itself becomes one more client
instead of the sole owner.
"""
