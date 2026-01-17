import clr
import math
from System.Collections.Generic import List

# ------------------------------------------------------------
# Load Revit API
# ------------------------------------------------------------
clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import *

clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager

doc = DocumentManager.Instance.CurrentDBDocument


# ------------------------------------------------------------
# Get all geometry vertices from an element
# This allows accurate dimension calculation
# ------------------------------------------------------------
def get_element_vertices(element):
    vertices = []

    options = Options()
    options.DetailLevel = ViewDetailLevel.Fine

    geometry = element.get_Geometry(options)

    if not geometry:
        return vertices

    for geo_obj in geometry:

        # Direct solids
        if isinstance(geo_obj, Solid) and geo_obj.Volume > 0:
            for edge in geo_obj.Edges:
                vertices.extend(edge.Tessellate())

        # Nested geometry (families, instances, etc.)
        elif isinstance(geo_obj, GeometryInstance):
            instance_geometry = geo_obj.GetInstanceGeometry()

            for inst_obj in instance_geometry:
                if isinstance(inst_obj, Solid) and inst_obj.Volume > 0:
                    for edge in inst_obj.Edges:
                        vertices.extend(edge.Tessellate())

    return vertices


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
FEET_TO_METERS = 0.3048

assemblies = (
    FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_Assemblies)
    .WhereElementIsNotElementType()
    .ToElements()
)

# Output table
data_export = []
data_export.append([
    "Assembly",
    "Total Length (m)",
    "Total Width (m)",
    "Total Height (m)",
    "Shipping Volume (m³)"
])


# ------------------------------------------------------------
# Main loop
# ------------------------------------------------------------
for assembly in assemblies:
    try:
        # Assembly transform defines its local orientation
        transform = assembly.GetTransform()
        inverse_transform = transform.Inverse

        member_ids = assembly.GetMemberIds()
        local_points = []

        # Collect geometry points from all assembly members
        for member_id in member_ids:
            element = doc.GetElement(member_id)
            if not element:
                continue

            world_points = get_element_vertices(element)

            # Convert world coordinates to assembly local coordinates
            for pt in world_points:
                local_pt = inverse_transform.OfPoint(pt)
                local_points.append(local_pt)

        if not local_points:
            continue

        # Calculate local extents
        xs = [p.X for p in local_points]
        ys = [p.Y for p in local_points]
        zs = [p.Z for p in local_points]

        length = (max(xs) - min(xs)) * FEET_TO_METERS
        width  = (max(ys) - min(ys)) * FEET_TO_METERS
        height = (max(zs) - min(zs)) * FEET_TO_METERS

        volume = length * width * height

        # Sort dimensions so "length" is always the largest
        dimensions = sorted([length, width, height], reverse=True)

        data_export.append([
            assembly.Name,
            round(dimensions[0], 3),
            round(dimensions[1], 3),
            round(dimensions[2], 3),
            round(volume, 3)
        ])

    except Exception as error:
        data_export.append([
            assembly.Name,
            0, 0, 0,
            "Error: {}".format(error)
        ])


# ------------------------------------------------------------
# Dynamo output
# ------------------------------------------------------------
OUT = data_export