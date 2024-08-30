# ResilientDeploymentSolver

Automated optimization solver for deploying distributed application components to remote embedded nodes using the RIAPS framework. Utilizes SMT constraint solver to find an optimal placement solution.

## Design

The deployment solver was implemented in Python and consists of three parts: 
- A deployment specification language dspec using which users can define specifications that are then parsed using a model
parser.
-  A constraint optimization solver implemented using Z3.
-  A deployment generator that converts the computed solution into a RIAPS deployment file. It takes as input a RIAPS model file app.riaps,
a deployment specification file app.dspec, a hardware configuration file hardware-spec.conf for resource
limits and produces as output a RIAPS deployment file app.depl.

It uses textX to create a new specification laguage in `depl_spec.tx` for users to provide their deplyoment  choices which are transformed into Z3 constraints.

## Constraint Types

The deployment solution space is encoded as a 2D deployment matrix where each element is a binary variable, $X$. The constraints are formally defined as:
- **Redundany**: $$\forall j ( \sum_i X_{i,j} = D(A_j))$$, where $D(A_j) \in \mathbb{N}$.
- **Host-actor dependency**: $$\forall j (Node_i \in H(A_j)) \implies (\forall p \neq i,\ X_{p,j} = 0)$$, where $H(A_j)$ denotes actor $A_j$ is dependent on host H.
- **Colocation**: $$\forall A_m, A_n \in C, (X_{i,m} = 1) \implies (X_{i,n} = 1)$$, where C is a set of actors that must be deployed to the same node. $C = \{ A_j | j \in \mathbb{N} \}$
- **Separation**: $$\forall A_m, A_n \in S, (X_{i,m} = 1) \implies (X_{i,n} = 0)$$, where S is a set of actors that can not be placed on the same node. $S = \{ A_j | j \in \mathbb{N} \wedge (A_j, A_k \in S \implies A_j, A_k \notin C.\ \forall i \neq j ) \}$.
- **CPU**: $$\forall i \sum_j (X_{i,j} \times cpu(A_j))/100*interval \\ < cpu_{max}(Node_i)/100*cores*interval$$, where CPU utilization ($cpu$, $cpu_{max}$ for worst-case) is per core up to total $cores$,  expressed as a percentage over $interval$.
- **Memory**: $$\forall i \sum_j (X_{i,j} \times mem(A_j)) < mem(Node_i)$$, memory ($mem$) expressed in MB.
- **Disk space**: $$\forall i \sum_j (X_{i,j} \times spc(A_j)) < spc(Node_i)$$, disk space ($spc$) expressed in MB.
- **Network bandwidth**: $$\forall i \sum_j (X_{i,j} \times rate(A_j))+Max(ceil_{j}-rate_{j}) \\ < 0.95*NIC\_RATE(Node_i)$$, average rate, ($rate$) and a maximum ceiling ($ceil$), expressed in kilobits per second (kbps).
