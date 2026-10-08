# AdFlow

AdFlow is a personalized advertising recommendation and experimentation platform demonstrated with synthetic data.

## Language

**Synthetic user**:
A fictional person represented by a generated profile and advertising interactions.
_Avoid_: Real customer

**Ad**:
An advertisement offered by an advertiser for selection and presentation to a synthetic user.

**Candidate**:
An ad considered for ranking for a particular recommendation.

**Ranking strategy**:
A rule for comparing candidate ads to choose a recommendation.

**Experiment variant**:
One of the ranking alternatives compared within an experiment.

**Traffic simulator**:
A reproducible source of recommendation requests and simulated user interactions.

**Simulated revenue**:
An accounting metric that credits the bid captured for a recommendation once when its click is accepted, rather than money received from real payments.
_Avoid_: Actual revenue

**Recommendation**:
A recorded selection of one ad for one synthetic user's ad opportunity, retaining its bid and any experiment attribution.

**Impression**:
A client's confirmation that the ad from a specific recommendation was displayed.
_Avoid_: Server selection, response sent

**Attributed click**:
A click linked to a specific recommendation with a confirmed impression.

**Ad opportunity**:
One request to select an ad; retries with the same request key refer to the same opportunity.

**No-ad outcome**:
An ad opportunity for which no eligible advertisement could be selected.
_Avoid_: Impression, recommendation

**Historical exposure**:
A generated past display of an eligible ad to a synthetic user, paired with a simulated click outcome for model development.
_Avoid_: Live experiment impression

**Click outcome**:
Whether a particular displayed ad receives a simulated click.

**Outcome generator**:
The simulated behavior rules that determine click tendencies independently of the ranking strategy's predictions.

**Simulation run**:
One identified demonstration of synthetic user activity against AdFlow.

**Candidate retrieval**:
The selection of a bounded set of eligible ads for a user's subsequent ranking.

**Interest similarity**:
The cosine similarity between a user's topic membership and an ad's combined interest/category membership.

**Eligible ad**:
An active ad belonging to an active advertiser at the time it is considered for selection.

**Predicted CTR**:
The model's estimated probability that a displayed ad will receive a click given its user/ad context.
_Avoid_: Guaranteed click rate, observed CTR

**Observed CTR**:
The fraction of counted impressions that received a counted click in a defined population and period.
_Avoid_: Predicted CTR

**Bid**:
The simulated dollars per accepted click offered for an ad and captured when that ad is recommended.

**Expected simulated value**:
Predicted CTR multiplied by bid, representing estimated simulated revenue per impression.
_Avoid_: Actual revenue, clearing price

**Experiment**:
A comparison of fixed ranking alternatives with stable synthetic-user assignment over a defined run.

**Assigned variant**:
The experiment group designated for a synthetic user, independently of whether an ad is successfully displayed.
_Avoid_: Exposure

**Exposed user**:
A synthetic user with at least one confirmed impression in the experiment reporting cohort.
_Avoid_: Attempted user, assigned user

**Recommendation cohort**:
Recommendations grouped by creation period, retaining their associated impressions and clicks even when those events arrive later.
