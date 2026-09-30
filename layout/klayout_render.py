# KLayout batch script: render a GDS to PNG with the SKY130 layer properties.
# usage: klayout -b -r klayout_render.py -rd gds=<in.gds> -rd png=<out.png> -rd lyp=<sky130A.lyp> [-rd w=2400 -rd h=1200] [-rd box=x0,y0,x1,y1]
import pya

w = int(globals().get("w", "2400"))
h = int(globals().get("h", "1200"))
view = pya.LayoutView()
view.set_config("background-color", globals().get("bg", "#ffffff"))
view.set_config("grid-visible", "false")
view.set_config("text-visible", "true")
view.set_config("default-text-size", "0.4")
view.load_layout(gds, 0)
view.load_layer_props(lyp)
view.max_hier()
view.zoom_fit()
if "box" in globals():                      # optional zoom window "x0,y0,x1,y1" in um
    x0, y0, x1, y1 = (float(v) for v in box.split(","))
    view.zoom_box(pya.DBox(x0, y0, x1, y1))
view.save_image(png, w, h)
print("wrote", png)
