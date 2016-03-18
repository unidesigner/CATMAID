/* -*- mode: espresso; espresso-indent-level: 2; indent-tabs-mode: nil -*- */
/* vim: set softtabstop=2 shiftwidth=2 tabstop=2 expandtab: */

(function(CATMAID) {

  "use strict";

  /**
   * This namespace provides functions to work with annotations on neurons. All
   * of them return promises.
   */
  var Nodes = {

    /**
     * Update the radius of a node.
     *
     * @returns A new promise that is resolved once the radius is updated. It
     *          contains all updated nodes along with their old radii.
     */
    updateRadius: function(projectId, nodeId, radius, updateMode) {
      CATMAID.requirePermission(projectId, 'can_annotate',
          'You don\'t have have permission to update the radius of a node');
      var url = projectId + '/treenode/' + nodeId + '/radius';
      var params = {
        radius: radius,
        option: updateMode
      };

      return CATMAID.fetch(url, 'POST', params).then(function(json) {
        return {
          // An object mapping node IDs to their old and new radius is returned.
          'updatedNodes': json.updated_nodes
        };
      });
    },

    /**
     * Update the radius of a list of nodes.
     *
     * @returns A new promise that is resolved once the radius is updated. It
     *          contains all updated nodes along with their old radii.
     */
    updateRadii: function(projectId, nodesVsRadii) {
      CATMAID.requirePermission(projectId, 'can_annotate',
          'You don\'t have have permission to update the radius of a node');
      var url = projectId + '/treenodes/radius';
      var treenodeIds = Object.keys(nodesVsRadii);
      var params = {
        treenode_ids: treenodeIds,
        treenode_radii: treenodeIds.map(function(tnid) {
          return nodesVsRadii[tnid];
        })
      };

      return CATMAID.fetch(url, 'POST', params).then(function(json) {
        return {
          // An object mapping node IDs to their old and new radius is returned.
          'updatedNodes': json.updated_nodes,
        };
      });
    },

    /**
     * Update confidence of a node to its parent.
     *
     * @returns A new promise that is resolved once the confidence has been
     *          successfully updated.
     */
    updateConfidence: function(projectId, nodeId, newConfidence, toConnector, partnerId) {
      CATMAID.requirePermission(projectId, 'can_annotate',
          'You don\'t have have permission to change the node confidence');

      var url = projectId + '/treenodes/' + nodeId + '/confidence';
      var params = {
        to_connector: toConnector,
        new_confidence: newConfidence,
      };
      if (partnerId) {
        params[partner_id] = partnerId;
      }

      return CATMAID.fetch(url, 'POST', params)
        .then((function(result) {
          this.trigger(CATMAID.Nodes.EVENT_NODE_CONFIDENCE_CHANGED, nodeId,
              newConfidence, result.updated_partners);
          return {
            'updatedPartners': result.updated_partners
          };
        }).bind(this));
    },

    /**
     * Override the parent of a particular node.
     */
    updateParent: function(projectId, nodeId, newParentId) {
      CATMAID.requirePermission(projectId, 'can_annotate',
          'You don\'t have have permission to change node');

      var url = projectId + '/treenode/' + nodeId + '/parent';
      var params = {
        parent_id: newParentId
      };

      return CATMAID.fetch(url, 'POST', params)
        .then(function(result) {
          CATMAID.Skeletons.trigger(CATMAID.Skeletons.EVENT_SKELETON_CHANGED,
              result.skeleton_id);
          return result;
        });
    },

    /**
     * Create a new treenode in a skeleton. If no parent is given, a new
     * skeleton is created.
     *
     * @param {integer} projectId  The project space to create the node in
     * @param {number}  x          The X coordinate of the node's location
     * @param {number}  y          The Y coordinate of the node's location
     * @param {number}  z          The Z coordinate of the node's location
     * @param {integer} parentId   (Optional) Id of the parent node of the new node
     * @param {number}  radius     (Optional) Radius of the new node
     * @param {integer} confidence (Optional) Confidence of edge to parent
     * @param {integer} useNeuron  (Optional) Target neuron ID to double check
     * @param {string}  neuronName (Optional) Naming pattern for new neuron
     *
     * @returns a promise that is resolved once the treenode is created
     */
    create: function(state, projectId, x, y, z, parentId, radius, confidence, useNeuron, neuronName) {
      CATMAID.requirePermission(projectId, 'can_annotate',
          'You don\'t have have permission to create a new node');

      var url = projectId + '/treenode/create';
      var params = {
        parent_id: parentId,
        x: x,
        y: y,
        z: z,
        radius: radius,
        confidence: confidence,
        useneuron: useNeuron,
        neuron_name: neuronName,
        state: JSON.stringify(state)
      };

      return CATMAID.fetch(url, 'POST', params)
        .then(function(result) {
          CATMAID.Nodes.trigger(CATMAID.Nodes.EVENT_NODE_CREATED,
              result.treenode_id, x, y, z);
          CATMAID.Skeletons.trigger(CATMAID.Skeletons.EVENT_SKELETON_CHANGED,
              result.skeleton_id);
          return result;
        });
    },

    /**
     * Insert a new treenode in a skeleton, optionally between two nodes. If no
     * parent is given, a new skeleton is created.
     *
     * @param {integer} projectId  The project space to create the node in
     * @param {number}  x          The X coordinate of the node's location
     * @param {number}  y          The Y coordinate of the node's location
     * @param {number}  z          The Z coordinate of the node's location
     * @param {integer} parentId   Id of the parent node of the new node
     * @param {integer} childId    Id of child to insert in edge
     * @param {number}  radius     (Optional) Radius of the new node
     * @param {integer} confidence (Optional) Confidence of edge to parent
     * @param {integer} useNeuron  (Optional) Target neuron ID to double check
     *
     * @returns a promise that is resolved once the treenode is created
     */
    insert: function(projectId, x, y, z, parentId, childId, radius, confidence, useNeuron) {
      CATMAID.requirePermission(projectId, 'can_annotate',
          'You don\'t have have permission to create a new node');

      var url = projectId + '/treenode/insert';
      var params = {
        parent_id: parentId,
        child_id: childId,
        x: x,
        y: y,
        z: z,
        radius: radius,
        confidence: confidence,
        useneuron: useNeuron
      };

      return CATMAID.fetch(url, 'POST', params)
        .then(function(result) {
          CATMAID.Nodes.trigger(CATMAID.Nodes.EVENT_NODE_CREATED,
              result.treenode_id, x, y, z);
          CATMAID.Skeletons.trigger(CATMAID.Skeletons.EVENT_SKELETON_CHANGED,
              result.skeleton_id);
          return result;
        });
    },

    /**
     * Delete a treenode.
     *
     * @param {integer} projectID  The project the treenode is part of
     * @param {integer} treenodeID The treenode to delete
     *
     * @returns promise deleting the treenode
     */
    remove: function(state, projectId, nodeId) {
      CATMAID.requirePermission(projectId, 'can_annotate',
          'You don\'t have have permission to remove a new node');

      var url = projectId + '/treenode/delete';
      var params = {
        treenode_id: nodeId,
        state: JSON.stringify(state)
      };

      return CATMAID.fetch(url, 'POST', params)
        .then(function(result) {
          // Emit deletion event, if the last node was removed and the neuron
          // deleted. Otherwise, trigger a change event for the neuron.
          var neuron_id = null;
          if (result.deleted_neuron) {
            CATMAID.Skeletons.trigger(CATMAID.Skeletons.EVENT_SKELETON_DELETED,
                result.skeleton_id);
          } else {
            CATMAID.Skeletons.trigger(CATMAID.Skeletons.EVENT_SKELETON_CHANGED,
                result.skeleton_id);
          }

          return result;
        });
    },

    /**
     * Update location of multiple treenodes and multiple connectors.
     *
     * @param {integer[]} treenodes  The list of four-element list each
     *                               containing a treenode ID and 3D location.
     * @param {integer[]} connectors The list of four-element list each
     *                               containing a connector ID and 3D location.
     *
     * @returns a promise resolving after the update succeeded
     */
    update: function(projectId, treenodes, connectors) {
      CATMAID.requirePermission(projectId, 'can_annotate',
          'You don\'t have have permission to update nodes');

      var url = projectId + '/node/update';
      var params = {
        t: treenodes,
        c: connectors
      };
      return CATMAID.fetch(url, 'POST', params)
        .then(function(result) {
          if (result.old_treenodes) {
            result.old_treenodes.forEach(announceNodeUpdate);
          }
          if (result.old_connectors) {
            result.old_connectors.forEach(announceNodeUpdate);
          }
          return result;
        });
    }

  };

  function announceNodeUpdate(node) {
    CATMAID.Nodes.trigger(CATMAID.Nodes.EVENT_NODE_UPDATED, node[0]);
  }

  // If annotations are deleted entirely
  Nodes.EVENT_NODE_CONFIDENCE_CHANGED = "node_confidence_changed";
  Nodes.EVENT_NODE_CREATED = "node_created";
  Nodes.EVENT_NODE_UPDATED = "node_updated";
  CATMAID.asEventSource(Nodes);

  // Export nodes
  CATMAID.Nodes = Nodes;

  CATMAID.UpdateNodeRadiusCommand = CATMAID.makeCommand(function(projectId,
        nodeId, radius, updateMode) {

    var exec = function(done, command) {
      var updateRadius = CATMAID.Nodes.updateRadius(projectId, nodeId,
          radius, updateMode);

      return updateRadius.then(function(result) {
        // The returned updatedNodes list contains objects with a node id and
        // the old radius.
        command._updatedNodes = result.updatedNodes;
        done();
        return result;
      });
    };

    var undo = function(done, command) {
      // Fail if expected undo parameters are not available from command
      if (undefined === command._updatedNodes) {
        throw new CATMAID.ValueError('Can\'t undo radius update, history data not available');
      }

      var oldRadii = Object.keys(command._updatedNodes).reduce(function(o, n) {
        o[n] = command._updatedNodes[n].old;
        return o;
      }, {});

      var updateRadii = CATMAID.Nodes.updateRadii(projectId, oldRadii);
      return updateRadii.then(done);
    };

    var info;
    if (updateMode && 0 !== updateMode) {
      if (1 === updateMode) {
        info = "Update radii of all nodes from " + nodeId +
            " to last branch (including) to be " + radius + "nm";
      } else if (2 === updateMode) {
        info = "Update radii of all nodes from " + nodeId +
            " to last branch (excluding) to be " + radius + "nm";
      } else if (3 === updateMode) {
        info = "Update radii of all nodes before " + nodeId +
            " to last without radius to be " + radius + "nm";
      } else if (4 === updateMode) {
        info = "Update radii of all nodes from " + nodeId +
            " to root to be " + radius + "nm";
      } else if (5 === updateMode) {
        info = "Update radii of all node " + nodeId +
            "'s skeleton to be " + radius + "nm";
      } else {
        info = "Update radius with unknown update mode";
      }
    } else {
      info = "Update radius of node " + nodeId + " to be " + radius + "nm";
    }
    this.init(info, exec, undo);
  });

  CATMAID.UpdateConfidenceCommand = CATMAID.makeCommand(function(
        projectId, nodeId, newConfidence, toConnector) {
    var exec = function(done, command) {
      var updateConfidence = CATMAID.Nodes.updateConfidence(projectId, nodeId,
          newConfidence, toConnector);

      return updateConfidence.then(function(result) {
        // The returned updatedNodes list contains objects with a node id and
        // the old radius.
        command._updatedPartners = result.updatedPartners;
        done();
        return result;
      });
    };

    var undo = function(done, command) {
      // Fail if expected undo parameters are not available from command
      if (undefined === command._updatedPartners) {
        throw new CATMAID.ValueError('Can\'t undo confidence update, ' +
            'history data not available');
      }

      var promises = Object.keys(command._updatedPartners).map(function(partnerId) {
        var oldConfidence = command._updatedPartners[partnerId];
        return CATMAID.Nodes.updateConfidence(projectId, nodeId, oldConfidence,
            toConnector, partnerId);
      });

      return Promise.all(promises);
    };

    var title;
    if (toConnector) {
      title = "Update confidence between node #" + nodeId +
        " and its linked connectors to " + newConfidence;
    } else {
      title = "Update confidence between node #" + nodeId +
        " and its parent to " + newConfidence;
    }

    this.init(title, exec, undo);
  });

  /**
   * Map a single node ID. The context is expected to be a CommandStore.
   */
  function mapNodeId(nodeId) {
    /* jshint validthis: true */ // "this" has to be a CommandStore instance
    return this.get(this.NODE, nodeId);
  }

  /**
   * Remove a node in an undoable fashion.
   *
   * @param {integer} projectId Project the node to remove is part of
   * @param {integer} nodeId    The node to remove
   */
  CATMAID.RemoveNodeCommand = CATMAID.makeCommand(function(
        state, projectId, nodeId) {

    var exec = function(done, command, map) {
      var removeNode = CATMAID.Nodes.remove(state, projectId, nodeId);

      return removeNode.then(function(result) {
        // Map ID of removed node to null to able to map the node created during
        // undo back to the original.
        map.add(map.NODE, nodeId, command);
        // Store information required for undo
        command.store('x', result.x);
        command.store('y', result.y);
        command.store('z', result.z);
        command.store('parentId', result.parent_id);
        command.store('childIds', result.child_ids);
        command.store('radius', result.radius);
        command.store('confidence', result.confidence);
        done();
        return result;
      });
    };

    var undo = function(done, command, map) {
      // Make sure we get the current IDs of the parent and former children,
      // which could have been modified through a redo operation.
      var mParentId = map.get(map.NODE, command.get('parentId'));
      // Obtain other parameters and validate
      var radius = command.get('radius');
      var confidence = command.get('confidence');
      var x = command.get('x'), y = command.get('y'), z = command.get('z');
      command.validateForUndo(confidence, mParentId, x, y, z);

      // Get IDs of previous children and map them to their current values
      var mChildIds = command.get('childIds').map(mapNodeId, map);

      // If there were child nodes before the removal, link to them again.
      var create;
      if (0 === mChildIds.length) {
        create = CATMAID.Nodes.create(state, projectId, x, y, z, mParentId, radius, confidence);
      } else {
        // Insert the node between parent and (first) child
        create = CATMAID.Nodes.insert(state, projectId, x, y, z, mParentId, mChildIds.shift(), radius, confidence);
      }
      return create.then(function(result) {
        // Store ID of new node created by this command
        map.add(map.NODE, result.treenode_id, command);
        var results = [result];
        // If there are more children, link them as well
        while (0 < mChildIds.length) {
          var childId = mChildIds.shift();
          var promise = CATMAID.Nodes.updateParent(projectId, childId, result.treenode_id);
          results.push(promise);
        }
        return Promise.all(results);
      }).then(function(results) {
        done();
        // Return result of actual node creation
        return results[0];
      });
    };

    var title = "Remove node #" + nodeId;

    this.init(title, exec, undo);
  });

  /**
   * Create a new treenode in a skeleton. If no parent is given, a new
   * skeleton is created. This command is reversible.
   *
   * @param {integer} projectId  The project space to create the node in
   * @param {number}  x          The X coordinate of the node's location
   * @param {number}  y          The Y coordinate of the node's location
   * @param {number}  z          The Z coordinate of the node's location
   * @param {integer} parentId   (Optional) Id of the parent node of the new node
   * @param {number}  radius     (Optional) Radius of the new node
   * @param {integer} confidence (Optional) Confidence of edge to parent
   * @param {integer} useNeuron  (Optional) Target neuron ID to double check
   * @param {string}  neuronName (Optional) Naming pattern for new neuron
   *
   * @returns a promise that is resolved once the treenode is created
   */
  CATMAID.CreateNodeCommand = CATMAID.makeCommand(function(
        state, projectId, x, y, z, parentId, radius, confidence, useNeuron, neuronName) {

    var exec = function(done, command, map) {
      // Get current, mapped version of parent ID
      var mParentId = map.get(map.NODE, parentId);
      var create = CATMAID.Nodes.create(state, projectId, x, y, z,
          mParentId, radius, confidence, useNeuron, neuronName);
      return create.then(function(result) {
        // Store ID of new node created by this command
        map.add(map.NODE, result.treenode_id, command);
        command.store('nodeId', result.treenode_id);
        done();
        return result;
      });
    };

    var undo = function(done, command, map) {
      var nodeId = map.get(map.NODE, command.get('nodeId'));
      command.validateForUndo(projectId, nodeId);
      var removeNode = CATMAID.Nodes.remove(projectId, nodeId);
      return removeNode.then(done);
    };

    var title = "Create new node with parent " + parentId + " at (" +
        x + ", " + y + ", " + z + ")";

    this.init(title, exec, undo);
  });

  /**
   * Insert a new treenode in a skeleton, optionally between two nodes. If no
   * parent is given, a new skeleton is created. This action is reversible.
   *
   * @param {integer} projectId  The project space to create the node in
   * @param {number}  x          The X coordinate of the node's location
   * @param {number}  y          The Y coordinate of the node's location
   * @param {number}  z          The Z coordinate of the node's location
   * @param {integer} parentId   Id of the parent node of the new node
   * @param {integer} childId    Id of child to insert in edge
   * @param {number}  radius     (Optional) Radius of the new node
   * @param {integer} confidence (Optional) Confidence of edge to parent
   * @param {integer} useNeuron  (Optional) Target neuron ID to double check
   *
   * @returns a promise that is resolved once the treenode is created
   */
  CATMAID.InsertNodeCommand = CATMAID.makeCommand(function(
      state, projectId, x, y, z, parentId, childId, radius, confidence, useNeuron) {

    var exec = function(done, command, map) {
      // Get current, mapped version of parent and child ID
      var mParentId = map.get(map.NODE, parentId);
      var mChildId = map.get(map.NODE, childId);
      var insert = CATMAID.Nodes.insert(state, projectId, x, y, z,
          mParentId, mChildId, radius, confidence, useNeuron);
      return insert.then(function(result) {
        // Store ID of new node created by this command
        map.add(map.NODE, result.treenode_id, command);
        command.store('nodeId', result.treenode_id);
        done();
        return result;
      });
    };

    var undo = function(done, command, map) {
      var nodeId = map.get(map.NODE, command.get('nodeId'));
      command.validateForUndo(projectId, nodeId);
      var removeNode = CATMAID.Nodes.remove(projectId, nodeId);
      return removeNode.then(done);
    };

    var title = "Inset new node between parent #" + parentId + " and child #" +
        childId + " at (" + x + ", " + y + ", " + z + ")";

    this.init(title, exec, undo);
  });

  /**
   * Map a node update list (list of four-element list with the first being the
   * node ID. The context is expected to be a CommandStore.
   */
  function mapNodeUpdateList(node) {
    /* jshint validthis: true */ // "this" has to be a CommandStore instance
    return [this.get(this.NODE, node[0]), node[1], node[2], node[3]];
  }

  /**
   * Map a connector update list (list of four-element list with the first being
   * the node ID. The context is expected to be a CommandStore.
   */
  function mapConnectorUpdateList(node) {
    /* jshint validthis: true */ // "this" has to be a CommandStore instance
    return [this.get(this.CONNECTOR, node[0]), node[1], node[2], node[3]];
  }

  /**
   * Update one or more treenodes and connectors.
   */
  CATMAID.UpdateNodesCommand = CATMAID.makeCommand(
      function(projectId, treenodes, connectors) {
    var exec = function(done, command, map) {
      var mTreenodes = treenodes ?  treenodes.map(mapNodeUpdateList, map) : undefined;
      var mConnectors = connectors ? connectors.map(mapConnectorUpdateList, map) : undefined;
      var update = CATMAID.Nodes.update(projectId, mTreenodes, mConnectors);
      return update.then(function(result) {
        // Save updated nodes with their old positions
        command.store('old_treenodes', result.old_treenodes);
        command.store('old_connectors', result.old_connectors);
        done();
        return result;
      });
    };

    var undo = function(done, command, map) {
      var old_treenodes = command.get('old_treenodes');
      var old_connectors = command.get('old_connectors');
      var mTreenodes = old_treenodes ? old_treenodes.map(mapNodeUpdateList, map) : undefined; 
      var mConnectors = old_connectors ? old_connectors.map(mapConnectorUpdateList, map) : undefined;
      var update = CATMAID.Nodes.update(projectId, mTreenodes, mConnectors);
      return update.then(function(result) {
        done();
        return result;
      });
    };

    var nTreenodes = treenodes ? treenodes.length : 0;
    var nConnectors = connectors ? connectors.length : 0;
    var title;
    if (nTreenodes > 0 && nConnectors > 0) {
      title = "Update " + nTreenodes + " treenode(s) and " +
        nConnectors + " connectors";
    } else if (nTreenodes > 0) {
      title = "Update " + nTreenodes + " treenode(s)";
    } else if (nConnectors > 0) {
      title = "Update " + nConnectors + " connector(s)";
    } else {
      title = "No-op: update no treenods and connectors";
    }

    this.init(title, exec, undo);
  });

})(CATMAID);
