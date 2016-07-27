# /usr/bin/python3

import sqlalchemy as sqla
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base

import geoalchemy2

import shapely.wkb
from shapely.geometry import Point, LineString

import fiona
import fiona.crs

import codecs
import errno

# the following list of riverbanks has some, but not all the usecase tests
# we want to solve, but I will be expanding as I find new examples
# and osm_ids are changed
examples = (
    # L'Eygoutier section close to the Tennis Club du Littoral, Toulon
    147639843,  # section with centerline, flow-in and through 224939728, flow out 27335952
                # has branch
    147639869,  # section without centerline, no flow-in or flow-out lines
    147639871,  # section without centerline, flow-in 271441410
    147639931,  # section without centerline, flow-in close to 27046147
    147639837,  # calculated centerline coincides with flow-in point, but
                # centerline is 27554300 and flow-in is 27351558,
                # touches the first, but not the latter, they share endpoint
    147639884,  # has flow-in, centerline, flow-out 27554300, several branches
                # one is a tributary 31104263
    147639857,  # calculated centerline does not reach node at flow-in
                # real flow-in, centerline is 27554300, flow-out is 30839685
    147639874,  # 30847660 is flow-in, centerline, close to be flow-out but quite
                # no real flow-out
                # can we really do anything about it?
    147639890,  # simplest case, isolated rectangle, medial a straight segment,
                # skel includes the parted X   >----<
    147639834,  # slightly more complex, several segments, but still basically
                # >----<
    147639896,  # slightly more complex, flow-in close to medial, flow-out
                # deviates, complex
    )

# too much boilerplate!
e= sqla.create_engine ('postgresql:///gis')
S= orm.sessionmaker (bind=e)
s= S()
m= sqla.MetaData (e)
Base= declarative_base(metadata=m)

class OSM_Polygons (Base):
    __tablename__= 'planet_osm_polygon'
    __table_args__= { 'autoload': True }
    osm_id= sqla.Column (sqla.Integer, primary_key=True)
    way= sqla.Column (geoalchemy2.Geometry('POLYGON'))

class OSM_Lines (Base):
    __tablename__= 'planet_osm_line'
    __table_args__= { 'autoload': True }
    osm_id= sqla.Column (sqla.Integer, primary_key=True)
    way= sqla.Column (geoalchemy2.Geometry('POLYGON'))

class PgSkel (Base):
    __tablename__= 'planet_osm_riverbank_skel'
    __table_args__= { 'autoload': True }
    osm_id= sqla.Column (sqla.Integer, primary_key=True)
    way= sqla.Column (geoalchemy2.Geometry('POLYGON'))
    skel= sqla.Column (geoalchemy2.Geometry('POLYGON'))

class PgMedial (Base):
    __tablename__= 'planet_osm_riverbank_medial'
    __table_args__= { 'autoload': True }
    osm_id= sqla.Column (sqla.Integer, primary_key=True)
    way= sqla.Column (geoalchemy2.Geometry('POLYGON'))
    medial= sqla.Column (geoalchemy2.Geometry('POLYGON'))

# duration: 98509.429 ms
# rb_row= s.query (OSM_Polygons).filter (OSM_Polygons.osm_id==147639890).first()
# duration: 97956.329 ms
# skel_row= s.query (PgSkel).filter (PgSkel.osm_id==147639890).first()
# duration: 98038.505 ms
# medial_row= s.query (PgMedial).filter (PgMedial.osm_id==147639890).first()

# duration: 438905.214 ms
# create index planet_osm_polygon_osm_id on planet_osm_polygon (osm_id);
# duration: negligible :)
# foo= s.query (PgMedial).filter (PgMedial.osm_id==147639896).first()

# this is strange, I would expect codecs.decode() to accept bytes() only
# Out[38]: 'POLYGON ((661994.3 5329434.18,
#                     661995.1899999999 5329436.47,
#                     662006.21 5329433.42,
#                     662005.66 5329431.28,
#                     661994.3 5329434.18))'
# rb= shapely.wkb.loads (codecs.decode (str (rb_row.way), 'hex'))
# Out[39]: 'MULTILINESTRING ((661994.3 5329434.18, 661995.9207244834 5329435.013669997),
#                            (662005.66 5329431.28, 662004.8565612 5329432.636764912),
#                            (662006.21 5329433.42, 662004.8565612 5329432.636764912),
#                            (661995.1899999999 5329436.47, 661995.9207244834 5329435.013669997),
#                            (662004.8565612 5329432.636764912, 661995.9207244834 5329435.013669997))'
# skel= shapely.wkb.loads (codecs.decode (str (skel_row.skel), 'hex'))
# Out[40]: 'MULTILINESTRING ((662004.8565612 5329432.636764912, 661995.9207244834 5329435.013669997))'
# medial= shapely.wkb.loads (codecs.decode (str (medial_row.medial), 'hex'))

def way_skel_medial (osm_id):
    def get (table, osm_id):
        return s.query (table).filter (table.osm_id==osm_id).first ()

    def decode (way):
        return shapely.wkb.loads (codecs.decode (str (way), 'hex'))

    return (
        decode (get (OSM_Polygons, osm_id).way),
        decode (get (PgSkel, osm_id).skel),
        decode (get (PgMedial, osm_id).medial),
        )

# notice this:
# * rb is a list of 5 points, the last is teh same as the first
# * the only line in medial is the last line in skel

# nice:
# In [47]: l1= shapely.geometry.LineString ([(0, 0), (1, 1)])
# In [48]: l2= shapely.geometry.LineString ([(1, 1), (0, 0)])
# In [49]: l1.equals (l2)
# Out[49]: True

# and:
# In [62]: l1.touches (l1)
# Out[62]: False

# but:
# In [66]: l1.touches (shapely.geometry.Point (l1.coords[0]))
# Out[66]: True
# In [67]: l1.touches (shapely.geometry.Point (l1.coords[-1]))
# Out[67]: True


def medial_in_skel (skel, medial):
    """Finds the index of the LineString in skel that's the medial."""
    for index, line in enumerate (skel.geoms):
        if line.equals (medial.geoms[0]):
            return index

def radials (skel, medial):
    """Finds the LineStrings in skel that radiate from the ends of the medial."""
    start= Point (medial.geoms[0].coords[0])
    end= Point (medial.geoms[0].coords[-1])
    radials= [ [], [] ]

    for line in list (skel.geoms):
        if line.touches (start):
            radials[0].append (line)
        elif line.touches (end):
            radials[1].append (line)

    return radials

# in fact I need something more specific
def radial_points (way, skel, medial):
    """Finds the points on the radials that are on the way."""
    start= Point (medial.geoms[0].coords[0])
    end= Point (medial.geoms[0].coords[-1])
    radial_points= [[], []]

    for line in skel.geoms:
        # ignore medial
        if line.equals (medial.geoms[0]):
            continue

        if line.touches (start):
            points= [ Point (p) for p in line.coords ]
            point= [ p for p in points if p.touches (way) ][0]  # I know there's only one
            radial_points[0].append (point)
        elif line.touches (end):
            points= [ Point (p) for p in line.coords ]
            point= [ p for p in points if p.touches (way) ][0]  # I know there's only one
            radial_points[1].append (point)

    return radial_points

# even more specific
def flow_segments (way, skel, medial):
    """Returns the flow-in and flow-out segments in way."""
    points= radial_points (way, skel, medial)

    return ( LineString (points[0]), LineString (points[1]) )

# but not really, because the computations are done in Point()s anyways
def middle_point (p1, p2):
    """Returns the point between p1 and p2"""
    # Point does not have + or / defined!
    return Point (*[ (p1.coords[0][i]+p2.coords[0][i])/2 for i in (0, 1) ])

# finally we get somewhere
def extend_medial (way, skel, medial):
    """Extends medial with segments that go from the middle point of the
    way's flow segments to the ends of the medial."""
    ((p1, p2), (p3, p4))= radial_points (way, skel, medial)

    # now, p1, p2 are related to start
    # and p3, p4 to end
    # so it should be
    # [ middle_point (p1, p2), start, ..., end, middle_point (p3, p4) ]
    return LineString ([ middle_point (p1, p2), *medial.geoms[0].coords, middle_point (p3, p4) ])

def write (file_name, line):
    """Writes the LineString to the given filename, appending if the file already
    exists, or creating a new file if not."""
    try:
        f= fiona.open (file_name, 'a', driver='ESRI Shapefile',
                       crs=fiona.crs.from_epsg (900913),
                       schema=dict (geometry='LineString', properties={}))
    except OSError as e:
        # the file does not exist, create a new one
        f= fiona.open (file_name, 'w', driver='ESRI Shapefile',
                       crs=fiona.crs.from_epsg (900913),
                       schema=dict (geometry='LineString', properties={}))

    # prepare the record
    r= r= dict (geometry=dict (type='LineString', coordinates=l.coords),
                properties={})
    f.write (r)
    f.close ()
