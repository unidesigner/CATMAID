import itertools
import json
import math
import networkx as nx
import re

from collections import defaultdict

from django.db import connection
from django.http import HttpResponse, JsonResponse

from rest_framework.decorators import api_view

from catmaid import state
from catmaid.models import UserRole, Treenode, ClassInstance, \
        TreenodeConnector, Location
from catmaid.control.authentication import requires_user_role, \
        can_edit_class_instance_or_fail, can_edit_or_fail
from catmaid.control.common import get_relation_to_id_map, \
        get_class_to_id_map, insert_into_log, _create_relation
from catmaid.control.neuron import _delete_if_empty
from catmaid.control.node import _fetch_location, _fetch_locations
from catmaid.util import Point3D, is_collinear


def can_edit_treenode_or_fail(user, project_id, treenode_id):
    """ Tests if a user has permissions to edit the neuron which the skeleton of
    the treenode models."""
    info = _treenode_info(project_id, treenode_id)
    return can_edit_class_instance_or_fail(user, info['neuron_id'], 'neuron')


@requires_user_role(UserRole.Annotate)
def create_treenode(request, project_id=None):
    """
    Add a new treenode to the database
    ----------------------------------

    1. Add new treenode for a given skeleton id. Parent should not be empty.
       return: new treenode id
       If the parent's skeleton has a single node and belongs to the
       'Isolated synaptic terminals' group, then reassign ownership
       of the skeleton and the neuron to the user. The treenode remains
       property of the original user who created it.

    2. Add new treenode (root) and create a new skeleton (maybe for a given
       neuron) return: new treenode id and skeleton id.

    If a neuron id is given, use that one to create the skeleton as a model of
    it.
    """

    params = {}
    float_values = {
            'x': 0,
            'y': 0,
            'z': 0,
            'radius': 0}
    int_values = {
            'confidence': 0,
            'useneuron': -1,
            'parent_id': -1}
    string_values = {}
    for p in float_values.keys():
        params[p] = float(request.POST.get(p, float_values[p]))
    for p in int_values.keys():
        params[p] = int(request.POST.get(p, int_values[p]))
    for p in string_values.keys():
        params[p] = request.POST.get(p, string_values[p])

    # Make sure the back-end is in the expected state if the node should have a
    # parent
    parent_id = params['parent_id']
    if not parent_id or parent_id == -1:
        state.validate_parent_node_state(parent_id, request.POST.get('state'), True)

    treenode_id, skeleton_id = _create_treenode(project_id, request.user, request.user,
            params['x'], params['y'], params['z'], params['radius'],
            params['confidence'], params['useneuron'], params['parent_id'],
            neuron_name=request.POST.get('neuron_name', None))

    return HttpResponse(json.dumps({
        'treenode_id': treenode_id,
        'skeleton_id': skeleton_id
    }))

@requires_user_role(UserRole.Annotate)
def insert_treenode(request, project_id=None):
    """
    Create a new treenode between two existing nodes. Its creator and
    creation_date information will be set to information of child node. No node
    will be created, if the node on the edge between the given child and parent
    node.
    """
    # Use creation time, if part of parameter set
    params = {}
    float_values = {
        'x': 0,
        'y': 0,
        'z': 0,
        'radius': 0
    }
    int_values = {
        'confidence': 0,
        'parent_id': -1,
        'child_id': -1
    }
    for p in float_values.keys():
        params[p] = float(request.POST.get(p, float_values[p]))
    for p in int_values.keys():
        params[p] = int(request.POST.get(p, int_values[p]))

    # Find child and parent of new treenode
    child = Treenode.objects.get(pk=params['child_id'])
    parent = Treenode.objects.get(pk=params['parent_id'])

    # Make sure both nodes are actually child and parent
    if not child.parent == parent:
        raise ValueError('The provided nodes need to be child and parent')

    # Make sure the requested location for the new node is on the edge between
    # both existing nodes if the user has no edit permissions on the neuron.
    try:
        can_edit_treenode_or_fail(request.user, project_id, parent.id)
    except:
        child_loc = Point3D(child.location_x, child.location_y, child.location_z)
        parent_loc = Point3D(parent.location_x, parent.location_y, parent.location_z)
        new_node_loc = Point3D(params['x'], params['y'], params['z'])
        if not is_collinear(child_loc, parent_loc, new_node_loc, True):
            raise ValueError('New node location has to be between child and parent')

    # Use creator and creation time for neighboring node that was created last.
    if child.creation_time < parent.creation_time:
        user, time = parent.user, parent.creation_time
    else:
        user, time = child.user, child.creation_time

    # Create new treenode
    treenode_id, skeleton_id = _create_treenode(project_id, user, request.user,
            params['x'], params['y'], params['z'], params['radius'],
            params['confidence'], -1, params['parent_id'], time)

    # Update parent of child to new treenode
    child.parent_id = treenode_id
    child.save()

    return HttpResponse(json.dumps({
        'treenode_id': treenode_id,
        'skeleton_id': skeleton_id
    }))

def _create_treenode(project_id, creator, editor, x, y, z, radius, confidence,
                     neuron_id, parent_id, creation_time=None, neuron_name=None):

    relation_map = get_relation_to_id_map(project_id)
    class_map = get_class_to_id_map(project_id)

    def insert_new_treenode(parent_id=None, skeleton_id=None):
        """ If the parent_id is not None and the skeleton_id of the parent does
        not match with the skeleton.id, then the database will throw an error
        given that the skeleton_id, being defined as foreign key in the
        treenode table, will not meet the being-foreign requirement.
        """
        new_treenode = Treenode()
        new_treenode.user = creator
        new_treenode.editor = editor
        new_treenode.project_id = project_id
        if creation_time:
            new_treenode.creation_time = creation_time
        new_treenode.location_x = float(x)
        new_treenode.location_y = float(y)
        new_treenode.location_z = float(z)
        new_treenode.radius = int(radius)
        new_treenode.skeleton_id = skeleton_id
        new_treenode.confidence = int(confidence)
        if parent_id:
            new_treenode.parent_id = parent_id
        new_treenode.save()
        return new_treenode

    def relate_neuron_to_skeleton(neuron, skeleton):
        return _create_relation(creator, project_id,
                                relation_map['model_of'], skeleton, neuron)

    response_on_error = ''
    try:
        if -1 != int(parent_id):  # A root node and parent node exist
            # Raise an Exception if the user doesn't have permission to edit
            # the neuron the skeleton of the treenode is modeling.
            can_edit_treenode_or_fail(editor, project_id, parent_id)

            # Select the parent treenode for update to prevent race condition
            # updates to its skeleton ID while this node is being created.
            cursor = connection.cursor()
            cursor.execute('''
                SELECT t.skeleton_id FROM treenode t WHERE t.id = %s
                FOR NO KEY UPDATE OF t
                ''', (parent_id,))
            parent_skeleton_id = cursor.fetchone()[0]

            response_on_error = 'Could not insert new treenode!'
            new_treenode = insert_new_treenode(parent_id, parent_skeleton_id)

            return (new_treenode.id, parent_skeleton_id)
        else:
            # No parent node: We must create a new root node, which needs a
            # skeleton and a neuron to belong to.
            response_on_error = 'Could not insert new treenode instance!'

            new_skeleton = ClassInstance()
            new_skeleton.user = creator
            new_skeleton.project_id = project_id
            new_skeleton.class_column_id = class_map['skeleton']
            new_skeleton.name = 'skeleton'
            new_skeleton.save()
            new_skeleton.name = 'skeleton %d' % new_skeleton.id
            new_skeleton.save()

            if -1 != neuron_id:
                # Check that the neuron to use exists
                if 0 == ClassInstance.objects.filter(pk=neuron_id).count():
                    neuron_id = -1

            if -1 != neuron_id:
                # Raise an Exception if the user doesn't have permission to
                # edit the existing neuron.
                can_edit_class_instance_or_fail(editor, neuron_id, 'neuron')

                # A neuron already exists, so we use it
                response_on_error = 'Could not relate the neuron model to ' \
                                    'the new skeleton!'
                relate_neuron_to_skeleton(neuron_id, new_skeleton.id)

                response_on_error = 'Could not insert new treenode!'
                new_treenode = insert_new_treenode(None, new_skeleton.id)

                return (new_treenode.id, new_skeleton.id)
            else:
                # A neuron does not exist, therefore we put the new skeleton
                # into a new neuron.
                response_on_error = 'Failed to insert new instance of a neuron.'
                new_neuron = ClassInstance()
                new_neuron.user = creator
                new_neuron.project_id = project_id
                new_neuron.class_column_id = class_map['neuron']
                if neuron_name:
                    # Create a regular expression to find allowed patterns. The
                    # first group is the whole {nX} part, while the second group
                    # is X only.
                    counting_pattern = re.compile(r"(\{n(\d+)\})")
                    # Look for patterns, replace all {n} with {n1} to normalize.
                    neuron_name = neuron_name.replace("{n}", "{n1}")

                    if counting_pattern.search(neuron_name):
                        # Find starting values for each substitution.
                        counts = [int(m.groups()[1]) for m in counting_pattern.finditer(neuron_name)]
                        # Find existing matching neurons in database.
                        name_match = counting_pattern.sub("(\d+)", neuron_name)
                        name_pattern = re.compile(name_match)
                        matching_neurons = ClassInstance.objects.filter(
                                project_id=project_id,
                                class_column_id=class_map['neuron'],
                                name__regex=name_match).order_by('name')

                        # Increment substitution values based on existing neurons.
                        for n in matching_neurons:
                            for i, (count, g) in enumerate(zip(counts, name_pattern.search(n.name).groups())):
                                if count == int(g):
                                    counts[i] = count + 1

                        # Substitute values.
                        count_ind = 0
                        m = counting_pattern.search(neuron_name)
                        while m:
                            neuron_name = m.string[:m.start()] + str(counts[count_ind]) + m.string[m.end():]
                            count_ind = count_ind + 1
                            m = counting_pattern.search(neuron_name)

                    new_neuron.name = neuron_name
                else:
                    new_neuron.name = 'neuron'
                    new_neuron.save()
                    new_neuron.name = 'neuron %d' % new_neuron.id

                new_neuron.save()

                response_on_error = 'Could not relate the neuron model to ' \
                                    'the new skeleton!'
                relate_neuron_to_skeleton(new_neuron.id, new_skeleton.id)

                response_on_error = 'Failed to insert instance of treenode.'
                new_treenode = insert_new_treenode(None, new_skeleton.id)

                response_on_error = 'Failed to write to logs.'
                new_location = (new_treenode.location_x, new_treenode.location_y,
                                new_treenode.location_z)
                insert_into_log(project_id, creator.id, 'create_neuron',
                                new_location, 'Create neuron %d and skeleton '
                                '%d' % (new_neuron.id, new_skeleton.id))

                return (new_treenode.id, new_skeleton.id)

    except Exception as e:
        import traceback
        raise Exception("%s: %s %s" % (response_on_error, str(e),
                                       str(traceback.format_exc())))


@requires_user_role(UserRole.Annotate)
def update_parent(request, project_id=None, treenode_id=None):
    treenode_id = int(treenode_id)
    parent_id = int(request.POST.get('parent_id', -1))

    child = Treenode.objects.get(pk=treenode_id)
    parent = Treenode.objects.get(pk=parent_id)

    if (child.skeleton_id != parent.skeleton_id):
        raise Exception("Child node %s is in skeleton %s but parent node %s is in skeleton %s!", \
                        treenode_id, child.skeleton_id, parent_id, parent.skeleton_id)

    child.parent_id = parent_id
    child.save()

    return JsonResponse({
        'success': True,
        'node_id': child.id,
        'parent_id': child.parent_id,
        'skeleton_id': child.skeleton_id
    })

def update_node_radii(node_ids, radii, cursor=None):
    """Update radius of a list of nodes, returns old radii.

    Both lists/tupples and single values can be supplied.
    """
    # Make sure we deal with lists
    type_nodes = type(node_ids)
    if type_nodes not in (list, tuple):
        node_ids = (node_ids,)
    # If only one a single radius value is available, use it for every input
    # node ID.
    type_radii = type(radii)
    if type_radii not in (list, tuple):
        radii = len(node_ids) * (radii,)

    if len(node_ids) != len(radii):
        raise ValueError("Number of treenode doesn't match number of radii")

    invalid_radii = [r for r in radii if math.isnan(r)]
    if invalid_radii:
        raise ValueError("Some radii where not numbers: " +
                ", ".join(invalid_radii))

    # Make sure we have a database cursor
    cursor = cursor or connection.cursor()

    # Create a list of the form [(node id, radius), ...]
    node_radii = "(" + "),(".join(map(lambda (k,v): "{},{}".format(k,v),
            zip(node_ids, radii))) + ")"

    cursor.execute('''
	UPDATE treenode t SET radius = target.new_radius
	FROM (SELECT x.id, x.radius AS old_radius, y.new_radius
	      FROM treenode x
	      INNER JOIN (VALUES {}) y(id, new_radius)
	      ON x.id=y.id FOR UPDATE) target
	WHERE t.id = target.id
	RETURNING t.id, target.old_radius, target.new_radius;
    '''.format(node_radii))

    updated_rows = cursor.fetchall()
    if 0 == len(updated_rows):
        raise ValueError('Coudn\'t find treenode #' + treenode_id)
    return {r[0]: {'old': r[1], 'new': float(r[2])} for r in updated_rows}

@requires_user_role(UserRole.Annotate)
def update_radii(request, project_id=None):
    """Update the radius of one or more nodes"""
    treenode_ids = [int(v) for k,v in request.POST.iteritems() \
        if k.startswith('treenode_ids[')]
    radii = [float(v) for k,v in request.POST.iteritems() \
        if k.startswith('treenode_radii[')]

    updated_nodes = update_node_radii(treenode_ids, radii)

    return JsonResponse({
        'success': True,
        'updated_nodes': updated_nodes
    })

@requires_user_role(UserRole.Annotate)
def update_radius(request, project_id=None, treenode_id=None):
    treenode_id = int(treenode_id)
    radius = float(request.POST.get('radius', -1))
    if math.isnan(radius):
        raise Exception("Radius '%s' is not a number!" % request.POST.get('radius'))
    option = int(request.POST.get('option', 0))
    cursor = connection.cursor()

    def create_update_response(updated_nodes, radius):
        return JsonResponse({
            'success': True,
            'updated_nodes': updated_nodes,
            'new_radius': radius
        })

    if 0 == option:
        # Update radius only for the passed in treenode and return the old
        # radius.
        old_radii = update_node_radii(treenode_id, radius, cursor)
        return create_update_response(old_radii, radius)

    cursor.execute('''
    SELECT id, parent_id, radius
    FROM treenode
    WHERE skeleton_id = (SELECT t.skeleton_id FROM treenode t WHERE id = %s)
    ''' % treenode_id)

    if 1 == option:
        # Update radius from treenode_id to next branch or end node (included)
        children = defaultdict(list)
        for row in cursor.fetchall():
            children[row[1]].append(row[0])

        include = [treenode_id]
        c = children[treenode_id]
        while 1 == len(c):
            child = c[0]
            include.append(child)
            c = children[child]

        old_radii = update_node_radii(include, radius, cursor)
        return create_update_response(old_radii, radius)

    if 2 == option:
        # Update radius from treenode_id to prev branch node or root (excluded)
        parents = {}
        children = defaultdict(list)
        for row in cursor.fetchall():
            parents[row[0]] = row[1]
            children[row[1]].append(row[0])

        include = [treenode_id]
        parent = parents[treenode_id]
        while parent and parents[parent] and 1 == len(children[parent]):
            include.append(parent)
            parent = parents[parent]

        old_radii = update_node_radii(include, radius, cursor)
        return create_update_response(old_radii, radius)

    if 3 == option:
        # Update radius from treenode_id to prev node with radius (excluded)
        parents = {}
        for row in cursor.fetchall():
            if row[2] < 0 or row[0] == treenode_id: # DB default radius is 0 but is initialized to -1 elsewhere
                parents[row[0]] = row[1]

        include = [treenode_id]
        parent = parents[treenode_id]
        while parent in parents:
            include.append(parent)
            parent = parents[parent]

        old_radii = update_node_radii(include, radius, cursor)
        return create_update_response(old_radii, radius)

    if 4 == option:
        # Update radius from treenode_id to root (included)
        parents = {row[0]: row[1] for row in cursor.fetchall()}

        include = [treenode_id]
        parent = parents[treenode_id]
        while parent:
            include.append(parent)
            parent = parents[parent]

        old_radii = update_node_radii(include, radius, cursor)
        return create_update_response(old_radii, radius)

    if 5 == option:
        # Update radius of all nodes (in a single query)
        skeleton_id = Treenode.objects.filter(pk=treenode_id).values('skeleton_id')
        include = list(Treenode.objects.filter(skeleton_id=skeleton_id) \
                .values_list('id', flat=True))

        old_radii = update_node_radii(include, radius, cursor)
        return create_update_response(old_radii, radius)


# REMARK this function went from 1.6 seconds to 400 ms when de-modelized
@requires_user_role(UserRole.Annotate)
def delete_treenode(request, project_id=None):
    """ Deletes a treenode. If the skeleton has a single node, deletes the
    skeleton and its neuron. Returns the parent_id, if any."""
    treenode_id = int(request.POST.get('treenode_id', -1))
    # Raise an exception if the user doesn't have permission to edit the
    # treenode.
    can_edit_or_fail(request.user, treenode_id, 'treenode')
    # Raise an Exception if the user doesn't have permission to edit the neuron
    # the skeleton of the treenode is modeling.
    can_edit_treenode_or_fail(request.user, project_id, treenode_id)
    # Make sure the back-end is in the expected state
    state.validate_node_state(treenode_id, request.POST.get('state'), True)

    treenode = Treenode.objects.get(pk=treenode_id)
    parent_id = treenode.parent_id

    response_on_error = ''
    deleted_neuron = False
    try:
        if not parent_id:
            child_ids = []
            # This treenode is root.
            response_on_error = 'Could not retrieve children for ' \
                'treenode #%s' % treenode_id
            n_children = Treenode.objects.filter(parent=treenode).count()
            response_on_error = "Could not delete root node"
            if n_children > 0:
                # TODO yes you can, the new root is the first of the children,
                # and other children become independent skeletons
                raise Exception("You can't delete the root node when it "
                                "has children.")
            # Get the neuron before the skeleton is deleted. It can't be
            # accessed otherwise anymore.
            neuron = ClassInstance.objects.get(project_id=project_id,
                        cici_via_b__relation__relation_name='model_of',
                        cici_via_b__class_instance_a=treenode.skeleton)
            # Remove the original skeleton. It is OK to remove it if it only had
            # one node, even if the skeleton's user does not match or the user
            # is not superuser. Delete the skeleton, which triggers deleting
            # the ClassInstanceClassInstance relationship with neuron_id
            response_on_error = 'Could not delete skeleton.'
            # Extra check for errors, like having two root nodes
            count = Treenode.objects.filter(skeleton_id=treenode.skeleton_id) \
                .count()
            if 1 == count:
                # deletes as well treenodes that refer to the skeleton
                ClassInstance.objects.filter(pk=treenode.skeleton_id) \
                    .delete()
            else:
                return HttpResponse(json.dumps({"error": "Can't delete " \
                    "isolated node: erroneously, its skeleton contains more " \
                    "than one treenode! Check for multiple root nodes."}))

            # If the neuron modeled by the skeleton of the treenode is empty,
            # delete it.
            response_on_error = 'Could not delete neuron #%s' % neuron.id
            deleted_neuron = _delete_if_empty(neuron.id)

            if deleted_neuron:
                # Insert log entry for neuron deletion
                insert_into_log(project_id, request.user.id, 'remove_neuron',
                               (treenode.location_x, treenode.location_y, treenode.location_z),
                               'Deleted neuron %s and skeleton(s) %s.' % (neuron.id, treenode.skeleton_id))

        else:
            # Treenode is not root, it has a parent and perhaps children.
            # Reconnect all the children to the parent.
            response_on_error = 'Could not update parent id of children nodes'
            child_ids = list(Treenode.objects.filter(parent=treenode).values_list('id', flat=True))
            Treenode.objects.filter(id__in=child_ids).update(parent=treenode.parent)

        # Remove treenode
        response_on_error = 'Could not delete treenode.'
        Treenode.objects.filter(pk=treenode_id).delete()
        return JsonResponse({
            'x': treenode.location_x,
            'y': treenode.location_y,
            'z': treenode.location_z,
            'parent_id': parent_id,
            'child_ids': child_ids,
            'radius': treenode.radius,
            'confidence': treenode.confidence,
            'skeleton_id': treenode.skeleton_id,
            'deleted_neuron': deleted_neuron,
            'success': "Removed treenode successfully."
        })

    except Exception as e:
        raise Exception(response_on_error + ': ' + str(e))


def _treenode_info(project_id, treenode_id):
    c = connection.cursor()
    # (use raw SQL since we are returning values from several different models)
    c.execute("""
    SELECT
        treenode.skeleton_id,
        ci.name as skeleton_name,
        ci2.id as neuron_id,
        ci2.name as neuron_name
    FROM
        treenode,
        relation r,
        class_instance ci,
        class_instance ci2,
        class_instance_class_instance cici
    WHERE ci.project_id = %s
      AND treenode.id = %s
      AND treenode.skeleton_id = ci.id
      AND ci.id = cici.class_instance_a
      AND ci2.id = cici.class_instance_b
      AND cici.relation_id = r.id
      AND r.relation_name = 'model_of'
    """, (project_id, treenode_id))
    results = [
        dict(zip([col[0] for col in c.description], row))
        for row in c.fetchall()
    ]
    if (len(results) > 1):
        raise ValueError('Found more than one skeleton and neuron for '
                        'treenode %s' % treenode_id)
    elif (len(results) == 0):
        raise ValueError('No skeleton and neuron for treenode %s' % treenode_id)

    return results[0]


@api_view(['POST'])
@requires_user_role([UserRole.Annotate, UserRole.Browse])
def treenode_info(request, project_id=None, treenode_id=None):
    """Retrieve skeleton and neuron information about this treenode.
    ---
    type:
      skeleton_id:
        description: ID of the treenode's skeleton
        type: integer
        required: true
      skeleton_name:
        description: Name of the treenode's skeleton
        type: string
        required: true
      neuron_id:
        description: ID of the treenode's neuron
        type: integer
        required: true
      neuron_name:
        description: Name of the treenode's neuron
        type: string
        required: true
    """
    info = _treenode_info(int(project_id), int(treenode_id))
    return HttpResponse(json.dumps(info))


@requires_user_role([UserRole.Annotate, UserRole.Browse])
def find_children(request, project_id=None, treenode_id=None):
    try:
        tnid = int(treenode_id)
        cursor = connection.cursor()
        cursor.execute('''
            SELECT id, location_x, location_y, location_z
            FROM treenode
            WHERE parent_id = %s
            ''', (tnid,))

        children = [[row] for row in cursor.fetchall()]
        return HttpResponse(json.dumps(children), content_type='application/json')
    except Exception as e:
        raise Exception('Could not obtain next branch node or leaf: ' + str(e))


@api_view(['POST'])
@requires_user_role(UserRole.Annotate)
def update_confidence(request, project_id=None, treenode_id=None):
    """Update confidence of edge between a node to either its parent or its
    connectors.

    The connection between a node and its parent or the connectors it is linked
    to can be rated with a confidence value in the range 1-5. If connector links
    should be updated, one can limit the affected connections to a specific
    connector. Returned is an object, mapping updated partners to their old
    confidences.
    ---
    parameters:
      - name: new_confidence
        description: New confidence, value in range 1-5
        type: integer
        required: true
      - name: to_connector
        description: Whether all linked connectors instead of parent should be updated
        type: boolean
        required: false
      - name: partner_id
        description: Limit update to single connector if to_connector is true
        type: integer
        required: false
    type:
        message:
            type: string
            required: true
        updated_partners:
            type: object
            required: true
    """
    tnid = int(treenode_id)
    can_edit_treenode_or_fail(request.user, project_id, tnid)

    new_confidence = int(request.POST.get('new_confidence', 0))
    if new_confidence < 1 or new_confidence > 5:
        raise ValueError('Confidence not in range 1-5 inclusive.')

    to_connector = request.POST.get('to_connector', 'false') == 'true'
    partner_id = request.POST.get('partner_id', None)
    if partner_id:
        partner_id = int(partner_id)

    cursor = connection.cursor()
    if to_connector:
        if partner_id:
            constraints = "WHERE treenode_id = %s AND connector_id = %s" % (tnid, partner_id)
        else:
            constraints = "WHERE treenode_id = %s" % tnid

        # Could be more than one. The GUI doesn't allow for specifying to which one.
        cursor.execute('''
            UPDATE treenode_connector tc
            SET confidence = %s
            FROM (SELECT x.id, x.confidence AS old_confidence
                  FROM treenode_connector x
                  {}
                  ) target
            WHERE tc.id = target.id
            RETURNING tc.connector_id, target.old_confidence
        '''.format(constraints), (new_confidence,))
    else:
        cursor.execute('''
            UPDATE treenode t
            SET confidence = %s, editor_id = %s
            FROM (SELECT x.id, x.confidence AS old_confidence
                  FROM treenode x
                  WHERE id = %s) target
            WHERE t.id = target.id
            RETURNING t.parent_id, target.old_confidence
        ''', (new_confidence, request.user.id, tnid))

    updated_partners = cursor.fetchall()
    if len(updated_partners) > 0:
        location = Location.objects.filter(id=tnid).values_list('location_x',
                'location_y', 'location_z')[0]
        insert_into_log(project_id, request.user.id, "change_confidence", location, "Changed to %s" % new_confidence)
        return JsonResponse({
            'message': 'success',
            'updated_partners': {r[0]:r[1] for r in updated_partners}
        })

    # Else, signal error
    if to_connector:
        raise ValueError('Failed to update confidence between treenode %s and '
                'connector.' % tnid)
    else:
        raise ValueError('Failed to update confidence at treenode %s.' % tnid)

def _skeleton_as_graph(skeleton_id):
    # Fetch all nodes of the skeleton
    cursor = connection.cursor()
    cursor.execute('''
        SELECT id, parent_id
        FROM treenode
        WHERE skeleton_id=%s''', [skeleton_id])
    # Create a directed graph of the skeleton
    graph = nx.DiGraph()
    for row in cursor.fetchall():
        # row[0]: id
        # row[1]: parent_id
        graph.add_node(row[0])
        if row[1]:
            # Create directional edge from parent to child
            graph.add_edge(row[1], row[0])
    return graph


def _find_first_interesting_node(sequence):
    """ Find the first node that:
    1. Has confidence lower than 5
    2. Has a tag
    3. Has any connector (e.g. receives/makes synapse, markes as abutting, ...)
    Otherwise return the last node.
    """
    if not sequence:
        raise Exception('No nodes ahead!')

    if 1 == len(sequence):
        return sequence[0]

    cursor = connection.cursor()
    cursor.execute('''
    SELECT t.id, t.confidence, tc.relation_id, tci.relation_id
    FROM treenode t
         LEFT OUTER JOIN treenode_connector tc ON (tc.treenode_id = t.id)
         LEFT OUTER JOIN treenode_class_instance tci ON (tci.treenode_id = t.id)
    WHERE t.id IN (%s)
    ''' % ",".join(map(str, sequence)))

    nodes = {row[0]: row for row in cursor.fetchall()}
    for node_id in sequence:
        if node_id in nodes:
            props = nodes[node_id]
            # [1]: confidence
            # [2]: a treenode_connector.relation_id, e.g. presynaptic_to or postsynaptic_to
            # [3]: a treenode_class_instance.relation_id, e.g. labeled_as
            # 2 and 3 may be None
            if props[1] < 5 or props[2] or props[3]:
                return node_id
        else:
            raise Exception('Nodes of this skeleton changed while inspecting them.')

    return sequence[-1]


@requires_user_role([UserRole.Annotate, UserRole.Browse])
def find_previous_branchnode_or_root(request, project_id=None, treenode_id=None):
    try:
        tnid = int(treenode_id)
        alt = 1 == int(request.POST['alt'])
        skid = Treenode.objects.get(pk=tnid).skeleton_id
        graph = _skeleton_as_graph(skid)
        # Travel upstream until finding a parent node with more than one child
        # or reaching the root node
        seq = [] # Does not include the starting node tnid
        while True:
            parents = graph.predecessors(tnid)
            if parents: # list of parents is not empty
                tnid = parents[0] # Can ony have one parent
                seq.append(tnid)
                if 1 != len(graph.successors(tnid)):
                    break # Found a branch node
            else:
                break # Found the root node

        if seq and alt:
            tnid = _find_first_interesting_node(seq)

        return HttpResponse(json.dumps(_fetch_location(tnid)))
    except Exception as e:
        raise Exception('Could not obtain previous branch node or root:' + str(e))


@requires_user_role([UserRole.Annotate, UserRole.Browse])
def find_next_branchnode_or_end(request, project_id=None, treenode_id=None):
    try:
        tnid = int(treenode_id)
        skid = Treenode.objects.get(pk=tnid).skeleton_id
        graph = _skeleton_as_graph(skid)

        children = graph.successors(tnid)
        branches = []
        for child_node_id in children:
            # Travel downstream until finding a child node with more than one
            # child or reaching an end node
            seq = [child_node_id] # Does not include the starting node tnid
            branch_end = child_node_id
            while True:
                branchChildren = graph.successors(branch_end)
                if 1 == len(branchChildren):
                    branch_end = branchChildren[0]
                    seq.append(branch_end)
                else:
                    break # Found an end node or a branch node

            branches.append([child_node_id,
                             _find_first_interesting_node(seq),
                             branch_end])

        # If more than one branch exists, sort based on downstream arbor size.
        if len(children) > 1:
            branches.sort(
                   key=lambda b: len(nx.algorithms.traversal.depth_first_search.dfs_successors(graph, b[0])),
                   reverse=True)

        # Leaf nodes will have no branches
        if len(children) > 0:
            # Create a dict of node ID -> node location
            node_ids_flat = list(itertools.chain.from_iterable(branches))
            node_locations = {row[0]: row for row in _fetch_locations(node_ids_flat)}

        branches = [[node_locations[id] for id in branch] for branch in branches]
        return HttpResponse(json.dumps(branches))
    except Exception as e:
        raise Exception('Could not obtain next branch node or leaf: ' + str(e))
