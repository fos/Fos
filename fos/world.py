from pyglet.gl import *
from camera import *
from fos.actor import Box, Actor
from fos.transform import *

class Region(object):

    def __init__(self, regionname, resolution, transform = None, extent_min = None, extent_max = None ):
        """Create a Region which is a spatial reference system and acts as a container
        for Actors presenting datasets.

        Parameters
        ----------
        regionname : str
            The unique name of the Region
        transform : fos.transform.Transform3D
            The affine transformation of the Region, defining
            origo and the axes orientation, i.e. the local coordinate
            system of the Region
        resolution : 3-tuple of strings
            Identifiers of the "Unit of Measurement" ontology
            denoting the spatial metric for one unit for each spatial axes
        extent_min, extent_max : two 3x1 numpy.array
            Defines the minimum and maximum extent of the Region along
            all three axes. This implicitly defines an
            axis-aligned bounding box which can be overwritten by the
            addition of Actors bigger then the extent and calling the
            update() function of the Region

        Notes
        -----
        Regions can be overlapping.

        """
        super(Region,self).__init__()
        
        self.regionname = regionname
        if transform is None:
            self.transform = IdentityTransform()
        else:
            self.transform = transform
        self.resolution = resolution
        self.actors = {}
        
        if not extent_min is None and not extent_max is None:
            self.extent_min = np.array( extent_min, dtype = np.float32 )
            self.extent_max = np.array( extent_max, dtype = np.float32 )
            self.add_actor( Box( "AABB", self.extent_min, self.extent_max ) )
        else:
            self.extent_min = None
            self.extent_max = None

    def get_centroid(self, apply_transform = True):
        """Returns the centroid of the Region.

        Parameters
        ----------
        apply_transform : bool
            Applies the Region affine transformation to the centroid
            
        """
        if not self.extent_min is None and not self.extent_max is None:
            ret = np.vstack( (self.extent_min,self.extent_max) ).mean( axis = 0 )
        else:
            ret = np.zeros( (1,3), dtype = np.float32 )

        if apply_transform:
            ret = self.transform.apply( ret )
            
        return ret

    def get_extent_min(self, apply_transform = True):
        if not self.extent_min is None:
            ret = self.extent_min
        else:
            ret = np.zeros( (1,3), dtype = np.float32 )

        if apply_transform:
            ret = self.transform.apply( ret )

        return ret

    def get_extent_max(self, apply_transform = True):
        if not self.extent_max is None:
            ret = self.extent_max
        else:
            ret = np.zeros( (1,3), dtype = np.float32 )
            
        if apply_transform:
            ret = self.transform.apply( ret )

        return ret

    def update_extent(self):
        """
        Loop over all contained actors and query for the min/max extent
        and update the Region's extent accordingly
        """
        for name, actor in self.actors.items():
            if not self.extent_min is None:
                self.extent_min = np.vstack( (self.extent_min,actor.get_extent_min()) ).min( axis = 0 )
            else:
                self.extent_min = actor.get_extent_min()

            if not self.extent_max is None:
                self.extent_max = np.vstack( (self.extent_max,actor.get_extent_max()) ).max( axis = 0 )
            else:
                self.extent_max = actor.get_extent_max()

        # update AABB
        if "AABB" in self.actors:
            self.actors['AABB'].update( self.extent_min, self.extent_max, 0.0 )
        else:
            self.add_actor( Box( "AABB", self.extent_min, self.extent_max ) )

    def update(self):
        self.update_extent()

    def add_actor(self, actor, trigger_update = True):
        if actor in self.actors:
            print("Actor {0} already exist in Region {1}".format(actor.name, self.regionname) )
        else:
            self.actors[actor.name] = actor
            self.update()

    def remove_actor(self, actor, trigger_update = True):
        if isinstance( actor, Actor ):
            if actor.name in self.actors:
                del self.actors[actor.name]
                self.update()
            else:
                print("Actor {0} does not exist in Region {1}".format(actor.name, self.regionname) )
        elif isinstance( actor, str ):
            # actor is the unique name of the actor
            if actor in self.actors:
                del self.actors[actor]
                self.update()
            else:
                print("Actor {0} does not exist in Region {1}".format(actor.name, self.regionname) )
        else:
            print("Not a valid Actor instance or actor name.")

    def draw_actors(self):
        """ Draw all visible actors in the region
        """
        for k, actor in self.actors.items():
            if actor.visible:
                #print("Draw actor", actor.name)
                actor.draw()


class World(object):

    def __init__(self):
        self.regions = {}
        self.camera = SimpleCamera()

    def add_region(self, region):
        if region.regionname in self.regions:
            print("Region {0} already exist.".format(region.regionname))
        else:
            self.regions[region.regionname] = region

    def new_region(self, regionname, transform, resolution, extent = None ):
        if regionname in self.regions:
            print("Region {0} already exist.".format(regionname))
        else:
            self.regions[regionname] = Region( regionname = regionname, transform = transform, resolution = resolution, extent = extent )

    def add_actor_to_region(self, regionname, actor):
        if regionname in self.regions:
            self.regions[regionname].add_actor( actor )
        else:
            print("Create Region first before adding actors.")

    def remove_actor_from_region(self, regionname, actor):
        if regionname in self.regions:
            self.regions[regionname].remove_actor()
        else:
            print("Region {0} does not exist.".format(regionname))

    def set_camera(self, camera):
        self.camera = camera

    def get_camera(self):
        return self.camera

    def refocus_camera(self):
        # loop over all regions, get global min, max, centroid
        # set focus point to average, and location to centroid + 2x(max-min).z

        centroids = np.zeros( (len(self.regions), 3), dtype = np.float32 )
        maxextent = np.zeros( (len(self.regions), 3), dtype = np.float32 )
        minextent = np.zeros( (len(self.regions), 3), dtype = np.float32 )
        
        for i, region in enumerate(self.regions.items()):
            centroids[i,:] = region[1].get_centroid()
            maxextent[i,:] = region[1].get_extent_max()
            minextent[i,:] = region[1].get_extent_min()

        newfoc = centroids.mean( axis = 0 )
        self.camera.set_focal( newfoc )
        newloc = newfoc.copy()
        # move along z axes sufficiently far to see all the regions
        # TODO: better
        dist = maxextent.max( axis = 0 ) - minextent.min( axis = 0 )
        newloc[2] += dist[0] 
        self.camera.set_location( newloc, np.array([0.0,1.0,0.0]) )
        self.camera.update()

    def draw_all(self):
        """ Draw all actors
        """
        self.camera.draw()
        for k, region in self.regions.items():
            # use transformation matrix of the region to setup the modelview
            vsml.pushMatrix( vsml.MatrixTypes.MODELVIEW ) # in fact, push the camera modelview
            vsml.multMatrix( vsml.MatrixTypes.MODELVIEW, region.transform.get_transform_numpy() )
            glMatrixMode(GL_MODELVIEW)
            glLoadMatrixf(vsml.get_modelview())
            region.draw_actors()
            # take back the old camera modelview
            vsml.popMatrix( vsml.MatrixTypes.MODELVIEW )