#!/usr/bin/python
# -*- coding: utf-8 -*-

# usage:
#   when simulation is running you can abort by pressing C^c. The current
#   geometry will then be drawn. Press C^c again to exit right away.

# credit:
#   github: https://github.com/inconvergent/leaf (python 2 version)


import numpy as np
import cairo
from time import time as time
from time import strftime
import sys
from scipy.spatial import Delaunay,distance
from collections import defaultdict

def timeit(method):
  def timed(*args, **kw):
    ts = time()
    result = method(*args, **kw)
    te = time()
    print('{:s} took {:8.4f} sec'.format(method.__name__,te-ts))
    return result
  return timed


@timeit
def main():
  """
  time to load up the ponies
  """

  ## numpy functions

  cos       = np.cos
  sin       = np.sin
  arctan2   = np.arctan2
  sqrt      = np.sqrt
  random    = np.random.random
  pi        = np.pi
  ft        = np.float64
  bigint    = np.int64
  ones      = np.ones
  zeros     = np.zeros
  array     = np.array
  bool      = np.bool
  tile      = np.tile
  maximum   = np.maximum
  colstack  = np.column_stack
  rowstack  = np.row_stack
  hstack    = np.hstack
  vstack    = np.vstack
  triag     = Delaunay
  unique    = np.unique
  positive  = lambda a: a[a>-1]
  vectorize = np.vectorize
  logicNot  = np.logical_not
  square    = np.square
  linspace  = np.linspace
  cdist     = distance.cdist
  eye       = np.eye
  transpose = np.transpose
  ceil      = np.ceil
  reshape   = np.reshape
  npsum     = np.sum
  npall     = np.all


  ## GLOBAL-ISH CONSTANTS (SYSTEM RELATED)
  
  ## pixel size of canvas
  SIZE   = 700
  ## background color (white)
  BACK   = 1.
  ## foreground color (black)
  FRONT  = 0.
  ## filename of image
  OUT    = './img.leaf'
  ## size of pixels on canvas
  STP    = 1./SIZE
  ## center of canvas
  C      = 0.5
  ## radius of circle with source nodes
  RAD    = 0.4
  ## number of grains used to sand paint each vein node
  GRAINS = 1
  ## alpha channel when rendering
  ALPHA  = 1.
  ## because five is right out
  FOUR   = 4

  ## GLOBAL-ISH CONSTANTS (PHYSICAL PROPERTIES)
  
  ## minimum distance between source nodes
  sourceDist  = 7.*STP
  ## a source node dies when all approaching vein nodes are closer than this
  ## only killzone == veinNode == STP will cause consistently visible merging
  ## of branches in rendering.
  killzone    = STP
  ## radius of vein nodes when rendered
  veinNode    = STP
  ## maximum number of vein nodes
  vmax        = 1*1e7
  # number of inital source nodes
  sinit       = 10000
  # number of source nodes to attempt to add in each iteration
  sadd        = 2
  ## width of widest vein nodes when rendered
  rootW       = 0.02*SIZE*STP
  ## width of smallest vein nodes when rendered
  leafW       = 3.*STP
  ## number of root (vein) nodes
  rootNodes   = 1


  def ctxInit():
    """
    make the drawing board
    """
    sur = cairo.ImageSurface(cairo.FORMAT_ARGB32,SIZE,SIZE)
    ctx = cairo.Context(sur)
    ctx.scale(SIZE,SIZE)
    ctx.set_source_rgb(BACK,BACK,BACK)
    ctx.rectangle(0,0,1,1)
    ctx.fill()
    return sur,ctx
  sur,ctx = ctxInit()


  def stroke(x,y):
    """
    draw dot for each (x,y)
    """
    ctx.rectangle(x,y,1./SIZE,1./SIZE)
    ctx.fill()
    return
  vstroke = vectorize(stroke)


  def circ(x,y,cr):
    """
    draw circle for each (x,y) with radius cr
    """
    ctx.arc(x,y,cr,0,2.*pi)
    ctx.fill()
    return
  vcirc = vectorize(circ)


  def draw(P,W,o,XY):
    """
    draws the veins
    """

    ## simple vein width calculation
    for i in reversed(range(rootNodes,o)):
      ii = P[i]
      while ii>1:
        W[ii]+=1.
        ii = P[ii]

    wmax = W.max()
    W = sqrt(W/wmax)*rootW
    W[W<leafW] = leafW

    ## show vein nodes
    for i in reversed(range(rootNodes,o)):
      dxy = XY[P[i],:]-XY[i,:]
      a   = arctan2(dxy[1],dxy[0])
      s   = linspace(0,1,GRAINS)*veinNode
      xyp = XY[P[i],:] - array( cos(a),sin(a) )*s

      vcirc(xyp[0],xyp[1],[W[i]/2.]*GRAINS)

  def tesselation(tri):
    """
    show triangulation of all vein nodes
    """

    for s in tri.simplices:
      ## ignore the four "container vertices" in the corners
      if all(s>FOUR-1):
        xy = tri.points[s,:]
        ctx.move_to(xy[0,0],xy[0,1])
        for i in range(2):
          ctx.line_to(xy[i,0],xy[i,1])
        ctx.stroke()


  def randomPointsInCircle(n,xx=C,yy=C,rr=RAD):
    """
    get n random points in a circle.
    """

    ## random uniform points in a circle
    t        = 2.*pi*random(n)
    u        = random(n)+random(n)
    r        = zeros(n,dtype=ft)
    mask     = u>1.
    xmask    = logicNot(mask)
    r[mask]  = 2.-u[mask]
    r[xmask] = u[xmask]
    xyp      = colstack(( rr*r*cos(t),rr*r*sin(t) ))
    dartsxy  = xyp + array( [xx,yy] )

    return dartsxy


  def darts(n):
    """
    get at most n random, uniformly distributed, points in a circle.
    centered at (xx,yy), with radius rr. points are no closer to each other
    than sourceDist.
    """
    
    dartsxy = randomPointsInCircle(n)

    jj = []

    ## remove new nodes that are too close to other 
    ## new nodes
    dists = cdist(dartsxy,dartsxy,'euclidean')
    for j in range(n-1):
      if all( dists[j,j+1:] > sourceDist ):
        jj.append(j)

    res = dartsxy[array(jj,dtype=bigint),:]
    lenres = res.shape[0]

    return res,lenres


  def throwMoreDarts(XY,sXY,o,n):
    """
    does the same as darts, but adds to existing points, making sure that
    distances from new nodes to source and vein nodes is greater than
    sourceDist.
    """

    dartsxy = randomPointsInCircle(n)

    jj = []

    dartsV = cdist(dartsxy,  XY[:o,:],'euclidean')
    dartsS = cdist(dartsxy, sXY      ,'euclidean')

    ## remove new nodes that are too close to other 
    ## new nodes or existing nodes
    for j in range(n-1):

      if all(dartsV[j,:]>sourceDist) and\
         all(dartsS[j,:]>sourceDist):
        jj.append(j)
    
    res = rowstack(( sXY,dartsxy[array(jj,dtype=bigint)] ))
    lenres = res.shape[0]

    return res,lenres

  
  #@timeit
  def makeNodemap(snum,ldistVS,ltri,lXY,lsXY):
    """
    map and inverse map of relative neighboring vein nodes of all source nodes
    
    - SVdict[source node indices] = list with indices of neighboring vein nodes
    - VSdict[vein node indices] = list with indices of source nodes that have
        this vein as a neighbor

    u_i is relative neighbor of s if for all u_i:
      ||v-s|| < max{ ||u_i-s||, ||u_i-v|| }

      we save time by only checking the vein nodes that belong to the
      surounding simplices.
    """
    
    SVdict = {}
    VSdict = defaultdict(list)
    
    # simplex -> vertices
    p  = ltri.simplices
    # s -> simplex
    js = ltri.find_simplex(lsXY,bruteforce=True,tol=1e-10) 
    # s -> neighboring simplices including s
    neigh = colstack((ltri.neighbors[js],js))
    # s -> potential neighboring points
    vv = [ unique( positive( p[ns,:]-FOUR ) ) \
             for ns in neigh ]

    uniqvv = unique( hstack(vv) )
    vvdist = cdist( lXY[uniqvv,:],lXY[uniqvv,:],'euclidean')

    lind = array(range(uniqvv.shape[0]),dtype=int)

    for j,ii in enumerate(vv):
      iin = ii.shape[0]
      ## corresponds to
      #    local = [np.where(uniqvv==i)[0][0] for i in ii]
      #  that is, the local mapping of ii into uniqvv 
      #  uniqvv must be sorted and all elements in ii must be in uniqvv
      local = np.searchsorted(uniqvv, ii)
      ##  = max { ||u_i-s||, ||u_i-v|| }
      mas = maximum( vvdist[local,:][:,local], ldistVS[ii,j] )
      
      ## do all distance calculations locally:
      #mas = maximum( cdist( lXY[ii,:],lXY[ii,:],'euclidean'),
                       #ldistVS[ii,j] )

      ##        ||v-s|| < mas
      compare = reshape(ldistVS[ii,j],(iin,1)) < mas
      mask    = npsum(compare,axis=1) == iin-1
      maskn   = npsum(mask)

      SVdict[j]=ii[mask]
      [VSdict[i].append(j) for i in ii[mask]]

    return VSdict,SVdict

  ### INITIALIZE

  XY       = zeros((int(vmax),2),dtype=ft)
  P        = zeros(int(vmax),dtype=bigint)-1
  W        = zeros(int(vmax),dtype=float)
  sXY,snum = darts(sinit)

  distVS   = None
  nodemap  = None

  ## (START) VEIN NODES

  ## triangulation needs at least four initial points
  ## in addition we need the initial triangulation 
  ## to contain all source nodes
  ## remember that nodes in tri will be four indices higher than in X,Y

  o = rootNodes
  xyinit          = zeros( (FOUR,2) )
  xyinit[:FOUR,:] = array( [[0.,0.],[1.,0.],[1.,1.],[0.,1.]] )


  for i in range(rootNodes):
    t = random()*2.*pi
    xy = C  + array( [cos(t),sin(t)] )*RAD
    XY[i,:]          = xy

  ## QJ makes all added points appear in the triangulation
  ## if they are duplicates they are added by adding a random small number to
  ## the node.
  tri = triag( vstack(( xyinit,XY[:o,:]  )),
               incremental=True,
               qhull_options='QJ Qc')
  triadd = tri.add_points

  ### MAIN LOOP

  itt  = 0
  aggt = 0
  iti = time()

  tri_time = 0
  try:
    while True:

      ## distance: vein nodes -> source nodes
      distVS = cdist(XY[:o,:],sXY,'euclidean')
      
      ## this is where the magic might happen
      VSdict,SVdict = makeNodemap(snum,distVS,tri,XY,sXY)

      ## grow new vein nodes
      oo = o
      for i,jj in VSdict.items():
        mask = distVS[i,jj]<=killzone
        if jj and not any(mask):
          txy      = npsum( XY[i,:] -sXY[jj,:] ,axis=0)
          a        = arctan2( txy[1],txy[0] )
          xy       = array( [cos(a),sin(a)] )*veinNode
          XY[o,:]  = XY[i,:] - xy 
          P[o]     = i
          o       += 1
        
      ## mask out dead source nodes
      mask = ones(snum,dtype=bool)
      for j,ii in SVdict.items():
        if all(distVS[ii,j]<=killzone):
          mask[j]      = False
          mn           = ii.shape[0]
          txy          = XY[ii,:]-sXY[j,:]
          a            = arctan2( txy[:,1],txy[:,0] )
          xy           = colstack(( cos(a),sin(a) ))*veinNode
          XY[o:o+mn,:] = XY[ii,:] + xy 
          P[ o:o+mn  ] = ii
          o           += mn

      ## add new points to triangulation
      #triadd(XY[oo:o,:])
      
      tri_time_a = time()
      del(tri)
      tri = triag( vstack(( xyinit,XY[:o,:]  )),qhull_options='Pp')
      tri_time += time()-tri_time_a
      

      ## remove dead soure nodes
      sXY  = sXY[mask,:]
      snum = sXY.shape[0]

      #sXY,snum = throwMoreDarts(XY,sXY,o,sadd)

      #if snum<3 or itt > 299:
      if snum<3:
        break

      if not itt % 50:
        aggt += time()-iti
        print("""{} | #i: {:6d} | #s: {:9.2f} | """\
              """#vn: {:6d} | #sn: {:6d}"""\
              .format(strftime("%Y-%m-%d %H:%M:%S"),\
                               itt,aggt,o,snum))
        sys.stdout.flush()
        iti = time()

      itt += 1

  except KeyboardInterrupt:
    pass

  finally:

    ctx.set_source_rgb(FRONT,FRONT,FRONT)

    print('tri time: ' + str(tri_time))
    
    print('\ndrawing ...\n')
    draw(P,W,o,XY)

    ## save to file
    sur.write_to_png('{:s}.veins.png'.format(OUT))

  return


if __name__ == '__main__' :

  if True:
    import pstats
    import cProfile
    OUT = 'profile'
    pfilename = '{:s}.profile'.format(OUT)
    cProfile.run('main()',pfilename)
    p = pstats.Stats(pfilename)
    p.strip_dirs().sort_stats('cumulative').print_stats()
  else:
    main()

