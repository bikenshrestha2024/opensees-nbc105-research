"""Explicit project section adapters; never infer confined boundaries from a paper."""
import math

def validate_card(card):
 errors=[]
 for name in ('thickness_m','fc_MPa','fy_MPa','rho_vertical','rho_horizontal'):
  value=card.get(name)
  if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<=0:errors.append(name+' needs a positive measured/design input')
 for name in ('rho_vertical','rho_horizontal'):
  if isinstance(card.get(name),(int,float)) and card[name]>=1:errors.append(name+' must be a ratio below 1')
 if card.get('boundary_elements') is not False:errors.append('This adapter is for a core without special boundary elements; explicitly set boundary_elements=false')
 if card.get('confined_concrete'):errors.append('Confined concrete cannot be assigned by this no-boundary adapter')
 for name in ('reinforcement_source','concrete_source','steel_source','local_axis_evidence','softening_regularization_evidence'):
  if not str(card.get(name) or '').strip():errors.append(name+' missing')
 return errors

def define_lu_layered_section(ops,tag,layers,total_thickness_m):
 """Layers are actual plate material tags/thicknesses in local axes, kN-m units.
 Define PlaneStressUserMaterial/PlateFromPlaneStress/PlateRebar first using
 reviewed material cards. This deliberately supplies no default strengths.
 """
 if len(layers)<3:raise ValueError('At least three explicit layers required')
 if not math.isfinite(total_thickness_m) or total_thickness_m<=0:raise ValueError('Invalid wall thickness')
 flat=[]
 for layer in layers:
  mat=layer['material_tag'];t=layer['thickness_m']
  if not isinstance(mat,int) or isinstance(mat,bool) or mat<=0 or not math.isfinite(t) or t<=0:raise ValueError('Invalid material tag/layer thickness')
  flat.extend([mat,t])
 if abs(sum(x['thickness_m'] for x in layers)-total_thickness_m)>1e-8*total_thickness_m:raise ValueError('Layer thickness sum must equal physical thickness; avoid double-counting steel layers')
 ops.section('LayeredShell',tag,len(layers),*flat)

def define_esfi_panel(ops,tag,nodes,widths,thicknesses,fsam_tags):
 """No physical beam is created. Verify CCW nodes, vertical panel and local axes separately."""
 if len(nodes)!=4 or len(set(nodes))!=4:raise ValueError('Four distinct corner nodes required')
 m=len(widths)
 if m<2 or len(thicknesses)!=m or len(fsam_tags)!=m:raise ValueError('Use at least two separated macro-fibers; matching array lengths required')
 if any(not math.isfinite(x) or x<=0 for x in [*widths,*thicknesses]):raise ValueError('Positive finite dimensions required')
 if any(not isinstance(x,int) or isinstance(x,bool) or x<=0 for x in fsam_tags):raise ValueError('Explicit FSAM tags required')
 ops.element('E_SFI_MVLEM_3D',tag,*nodes,m,'-thick',*thicknesses,'-width',*widths,'-mat',*fsam_tags,'-CoR',.4,'-ThickMod',.63,'-Poisson',.25,'-Density',0.)
